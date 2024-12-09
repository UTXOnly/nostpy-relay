import asyncio
import json
import logging
import os
from typing import Any, Dict, Tuple

import aiohttp
import redis.asyncio as redis
import websockets
from aiohttp.client_exceptions import ClientConnectionError
import websockets.exceptions

from websocket_classes import ExtractedResponse, WebsocketMessages, SubscriptionMatcher

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.metrics import (
    CallbackOptions,
    Observation,
    get_meter_provider,
    set_meter_provider,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

AioHttpClientInstrumentor().instrument()

OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
EVENT_HANDLER_SVC = os.getenv("EVENT_HANDLER_SVC")
EVENT_HANDLER_PORT = os.getenv("EVENT_HANDLER_PORT")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_CHANNEL = "events_channel"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": "websocket_handler_otel"}))
)
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
span_processor = BatchSpanProcessor(otlp_exporter)
otlp_tracer = trace.get_tracer_provider().add_span_processor(span_processor)

resource = Resource.create({"service.name": "websocket-handler"})
metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT)
metric_reader = PeriodicExportingMetricReader(metric_exporter)

meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

meter = metrics.get_meter("example-meter", version="1.0")

redis_client = redis.from_url(f"redis://{REDIS_HOST}")

active_subscriptions = {}


def active_websockets_subscriptions_callback(options: CallbackOptions):
    """
    Callback to return the current number of active WebSocket subscriptions.
    """
    len_act_sub = len(active_subscriptions)
    logger.debug(f"Gauge callback - Active WebSocket subscriptions: {len_act_sub}")
    return [Observation(value=len_act_sub, attributes={})]


# Create an ObservableGauge
active_websockets_subs_gauge = meter.create_observable_gauge(
    name="active_websockets_subs",
    description="Active WebSocket subscriptions",
    unit="count",
    callbacks=[active_websockets_subscriptions_callback],
)


async def handle_websocket_connection(
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    conn = aiohttp.TCPConnector(limit=500)
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            async for message in websocket:
                try:
                    logger.debug(f"message in loop is {message}")
                    ws_message = message
                    if ws_message:
                        ws_message = WebsocketMessages(
                            message=json.loads(message),
                            websocket=websocket,
                            logger=logger,
                        )
                except json.JSONDecodeError as json_error:
                    logger.error(f"Error decoding JSON message: {json_error}")
                    continue

                if ws_message.event_type == "EVENT":
                    logger.debug(
                        f"Event to be sent payload is: {ws_message.event_payload} of type {type(ws_message.event_payload)}"
                    )
                    with tracer.start_as_current_span("send_event_to_handle") as span:
                        current_span = trace.get_current_span()
                        current_span.set_attribute(
                            "operation.name", "send.event.handler"
                        )
                        await send_event_to_handler(
                            session=session,
                            event_dict=dict(ws_message.event_payload),
                            websocket=websocket,
                        )
                elif ws_message.event_type == "REQ":
                    logger.debug(
                        f"Payload is {ws_message.event_payload} and of type: {type(ws_message.event_payload)}"
                    )
                    with tracer.start_as_current_span(
                        "send_event_to_subscription"
                    ) as span:
                        current_span = trace.get_current_span()
                        current_span.set_attribute(
                            "operation.name", "send.event.subscription"
                        )
                        await send_subscription_to_handler(
                            session=session,
                            event_dict=ws_message.event_payload,
                            subscription_id=ws_message.subscription_id,
                            websocket=websocket,
                        )
                    active_subscriptions[ws_message.subscription_id] = {
                        "event": ws_message.event_payload,
                        "websocket": websocket,
                    }
                    logger.info(
                        f"Stored subscription: {ws_message.subscription_id} with event {ws_message.event_payload}"
                    )
                elif ws_message.event_type == "CLOSE":
                    response: Tuple[str, str] = (
                        "CLOSED",
                        ws_message.subscription_id,
                        "error: shutting down idle subscription",
                    )
                    await websocket.send(json.dumps(response))
                    del active_subscriptions[ws_message.subscription_id]

        except (websockets.exceptions.ConnectionClosedError, 
                ClientConnectionError, 
                aiohttp.ClientError, 
                Exception) as error:
            logger.error(f"An error occurred while processing the WebSocket message: {error}", exc_info=True)



async def send_event_to_handler(
    session: aiohttp.ClientSession,
    event_dict: Dict[str, Any],
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    url: str = f"http://{EVENT_HANDLER_SVC}:{EVENT_HANDLER_PORT}/new_event"
    try:
        async with session.post(url, data=json.dumps(event_dict)) as response:
            current_span = trace.get_current_span()
            current_span.set_attribute("operation.name", "post.event.handler")
            response_data: Dict[str, Any] = await response.json()
            logger.debug(
                f"Received response from Event Handler {response_data}, data types is {type(response_data)}"
            )
            response_object = ExtractedResponse(response_data, logger)
            if response.status:
                formatted_response = await response_object.format_response()
                await websocket.send(json.dumps(formatted_response))
    except Exception as e:
        logger.error(f"An error occurred while sending the event to the handler: {e}")


async def send_subscription_to_handler(
    session: aiohttp.ClientSession,
    event_dict: Dict,
    subscription_id: str,
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    url: str = f"http://{EVENT_HANDLER_SVC}:{EVENT_HANDLER_PORT}/subscription"

    payload: Dict[str, Any] = {
        "event_dict": event_dict,
        "subscription_id": subscription_id,
    }
    logger.debug(f"send payload is {payload}")

    async with session.post(url, data=json.dumps(payload)) as response:
        current_span = trace.get_current_span()
        current_span.set_attribute("operation.name", "post.event.subscription")
        response_data = await response.json()
        logger.debug(
            f"Data type of response_data: {type(response_data)}, Response Data: {response_data}"
        )
        if not response_data:
            logger.debug("Response data none, returning")
            await websocket.send(json.dumps(["EOSE", subscription_id]))
            return
        response_object = ExtractedResponse(response_data, logger)
        EOSE = "EOSE", response_object.subscription_id

        if response.status == 200 and response_object.event_type == "EVENT":
            with tracer.start_as_current_span("send event loop") as span:
                current_span = trace.get_current_span()
                current_span.set_attribute("operation.name", "send.event.loop")

                await response_object.send_event_loop(
                    response_object.results, websocket
                )
                await websocket.send(json.dumps(EOSE))
        else:
            await websocket.send(json.dumps(EOSE))
            logger.debug(f"Response data is {response_data} but it failed")


async def redis_listener():
    """Listens for Redis pub/sub messages and rebroadcasts to active WebSocket clients."""
    try:
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(REDIS_CHANNEL)
            logger.info(f"Subscribed to Redis channel: {REDIS_CHANNEL}")

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    logger.debug(f"Received message from Redis: {message}")
                    if message["type"] == "message":
                        try:
                            event_data = json.loads(message["data"].decode("utf-8"))
                            logger.debug(f"Decoded event data: {event_data}")
                            asyncio.create_task(broadcast_event_to_clients(event_data))
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in Redis message: {e}")
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error in Redis listener: {e}", exc_info=True)


async def broadcast_event_to_clients(event_data: Dict[str, Any]) -> None:
    """Broadcasts an event to all active WebSocket clients."""
    logger.debug(f"Active subscriptions: {active_subscriptions}")

    async def process_subscription(subscription_id, data):
        websocket = data["websocket"]
        try:
            matcher = SubscriptionMatcher(subscription_id, data["event"], logger)
            if matcher.match_event(event_data):
                await websocket.send(
                    json.dumps((f"EVENT", subscription_id, event_data))
                )
        except Exception as e:
            logger.error(f"Error broadcasting to subscription {subscription_id}: {e}")
            del active_subscriptions[subscription_id]

    # Process all subscriptions concurrently
    await asyncio.gather(
        *(
            process_subscription(subscription_id, data)
            for subscription_id, data in active_subscriptions.copy().items()
        )
    )


async def remove_inactive_websockets():
    """Periodically checks and removes inactive WebSocket connections."""
    while True:
        for subscription_id, data in list(active_subscriptions.items()):
            websocket = data["websocket"]
            try:
                if websocket.closed:
                    logger.info(f"Removing inactive WebSocket: {subscription_id}")
                    del active_subscriptions[subscription_id]
            except Exception as e:
                logger.error(f"Error checking WebSocket {subscription_id}: {e}")
                del active_subscriptions[subscription_id]
        await asyncio.sleep(10)


async def main():
    """Starts the WebSocket server and Redis listener."""
    websocket_port = int(os.getenv("WS_PORT", 8000))
    websocket_server = websockets.serve(
        handle_websocket_connection, "0.0.0.0", websocket_port
    )
    logger.info(f"WebSocket server starting on port {websocket_port}")

    # Create tasks for both the WebSocket server and Redis listener
    asyncio.create_task(redis_listener())
    asyncio.create_task(remove_inactive_websockets())
    await websocket_server

    # Prevent the program from exiting
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error occurred while starting the server main loop: {e}")
