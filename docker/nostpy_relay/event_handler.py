import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict

import psycopg
import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.metrics import Observation
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.trace import SpanAttributes
import orjson
from psycopg_pool import AsyncConnectionPool

from event_classes import Event, Subscription
from init_db import initialize_db
from otel_metric_base.otel_metrics import OtelMetricBase
from utils import LimitedDict


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

WOT_ENABLED = os.getenv("WOT_ENABLED")
REDIS_CHANNEL = "new_events_channel"

app = FastAPI()

trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": "event_handler_otel"}))
)
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

redis_tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": "redis"})
)
redis_otlp_exporter = OTLPSpanExporter()
redis_span_processor = BatchSpanProcessor(redis_otlp_exporter)
redis_tracer_provider.add_span_processor(redis_span_processor)
RedisInstrumentor().instrument(tracer_provider=redis_tracer_provider)


otel_metrics = OtelMetricBase(otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
metric_counters = {
    "wot_event_reject": LimitedDict(max_size=500),
    "event_added": LimitedDict(max_size=500),
    "event_query": LimitedDict(max_size=500),
}


def increment_counter(tags: Dict[str, str], counter_dict: LimitedDict):
    tag_key = str(sorted(tags.items()))
    counter_dict.setdefault(tag_key, {"count": 0, "tags": tags})["count"] += 1


def create_observable_callback(counter_dict: Dict[str, Dict[str, Any]]) -> Callable:
    def observable_callback(_):
        return [
            Observation(entry["count"], entry["tags"])
            for entry in counter_dict.values()
        ]

    return observable_callback


def register_metric(name: str, description: str):
    otel_metrics.meter.create_observable_counter(
        name=name,
        description=description,
        callbacks=[create_observable_callback(metric_counters[name])],
    )


register_metric("wot_event_reject", "Rejected note from WoT filter")
register_metric("event_added", "Event added")
register_metric("event_query", "Event query")


def get_conn_str(db_suffix: str) -> str:
    return (
        f"dbname={os.getenv(f'PGDATABASE_{db_suffix}')} "
        f"user={os.getenv(f'PGUSER_{db_suffix}')} "
        f"password={os.getenv(f'PGPASSWORD_{db_suffix}')} "
        f"host={os.getenv(f'PGHOST_{db_suffix}')} "
        f"port={os.getenv(f'PGPORT_{db_suffix}')} "
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn_str_write = get_conn_str("WRITE")
    conn_str_read = get_conn_str("READ")
    logger.info(f"Write conn string is: {conn_str_write}")
    logger.info(f"Read conn string is: {conn_str_read}")

    # Define limits for the connection pools
    app.write_pool = AsyncConnectionPool(
        conninfo=conn_str_write,
        timeout=30,  # Timeout in seconds for acquiring a connection
    )
    app.read_pool = AsyncConnectionPool(conninfo=conn_str_read, timeout=30)

    try:
        yield
    finally:
        await app.write_pool.close()
        await app.read_pool.close()


app = FastAPI(lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)
init_conn_str = get_conn_str("WRITE")


async def set_span_attributes(
    span, db_system: str, db_statement: str, service_name: str, operation_name: str
):
    span.set_attribute(SpanAttributes.DB_SYSTEM, db_system)
    span.set_attribute(SpanAttributes.DB_STATEMENT, db_statement)
    span.set_attribute("service.name", service_name)
    span.set_attribute("operation.name", operation_name)


async def execute_sql_with_tracing(app, sql_query: str, span_name: str):
    with tracer.start_as_current_span(span_name) as span:
        current_span = trace.get_current_span()
        await set_span_attributes(
            current_span, "postgresql", sql_query, "postgres", "postgres.query"
        )
        async with app.read_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query=sql_query)
                return await cur.fetchall()


async def get_redis_client() -> redis.Redis:
    """Lazily initialize and return an async Redis client."""
    return await redis.from_url(
        f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}",
        decode_responses=True,
    )


@app.post("/new_event")
async def handle_new_event(request: Request) -> JSONResponse:
    event_dict = orjson.loads(await request.body())
    event_obj = Event(
        event_id=event_dict["id"],
        pubkey=event_dict["pubkey"],
        kind=event_dict["kind"],
        created_at=event_dict["created_at"],
        tags=event_dict["tags"],
        content=event_dict["content"],
        sig=event_dict["sig"],
    )
    logger.debug(
        f"New event loop iter, event id is {event_obj.event_id} and kind is {event_obj.kind}"
    )

    try:
        with tracer.start_as_current_span("add_event") as span:
            current_span = trace.get_current_span()
            current_span.set_attribute(SpanAttributes.DB_SYSTEM, "postgresql")

            # Verify signature for all events before proceeding
            if not event_obj.verify_signature(logger):
                return event_obj.evt_response(
                    results_status="false",
                    http_status_code=400,
                    message="invalid: signature verification failed",
                )

            async with request.app.write_pool.connection() as conn:
                async with conn.cursor() as cur:
                    otel_tags = {
                        "kind": event_obj.kind,
                        "pubkey": event_obj.pubkey,
                        "event_id": event_obj.event_id,
                    }
                    if WOT_ENABLED in ["True", "true"]:
                        wot_check = await event_obj.check_wot(cur)
                        if not wot_check:
                            logger.debug(f"allow check failed: {wot_check}")
                            increment_counter(
                                otel_tags, metric_counters["wot_event_reject"]
                            )
                            return event_obj.evt_response(
                                results_status="false",
                                http_status_code=403,
                                message="rejected: user is not in relay's web of trust",
                            )

                    redis_client = await get_redis_client()

                    if event_obj.kind in [0, 3]:
                        await event_obj.delete_check(conn, cur)
                        await event_obj.add_event(conn, cur)
                        await redis_client.publish(
                            REDIS_CHANNEL, orjson.dumps(event_dict)
                        )
                        return event_obj.evt_response(
                            results_status="true", http_status_code=200
                        )

                    if event_obj.kind == 5:
                        events_to_delete = event_obj.parse_kind5()
                        await event_obj.delete_event(conn, cur, events_to_delete)
                        return event_obj.evt_response(
                            results_status="true", http_status_code=200
                        )

                    else:
                        try:
                            await event_obj.add_event(conn, cur)
                            increment_counter(otel_tags, metric_counters["event_added"])
                            await redis_client.publish(
                                REDIS_CHANNEL, orjson.dumps(event_dict)
                            )
                            logger.info(
                                f"Published event {event_obj.event_id} to Redis"
                            )
                            return event_obj.evt_response(
                                results_status="true", http_status_code=200
                            )
                        except psycopg.IntegrityError:
                            await conn.rollback()
                            logger.info(
                                f"Event with ID {event_obj.event_id} already exists"
                            )
                            return event_obj.evt_response(
                                results_status="false",
                                http_status_code=409,
                                message="duplicate: already have this event",
                            )
                        except Exception as exc:
                            logger.error(f"Exception adding event {exc}")
                            return event_obj.evt_response(
                                results_status="false",
                                http_status_code=400,
                                message="error: failed to add event",
                            )

    except Exception as exc:
        logger.debug(f"Exception while adding event to database: {exc}")
        await conn.rollback()
        return event_obj.evt_response(
            results_status="false",
            http_status_code=500,
            message="error: could not connect to the database",
        )


@app.post("/subscription")
async def handle_subscription(request: Request) -> JSONResponse:
    try:
        request_payload = orjson.loads(await request.body())
        logger.debug(f"Request payload is {request_payload}")

        subscription_obj = Subscription(request_payload)
        increment_counter({"stage": "pre-cache"}, metric_counters["event_added"])

        if not subscription_obj.filters:
            return subscription_obj.sub_response_builder(
                "EOSE", subscription_obj.subscription_id, "", 204
            )

        # Parse filters into query components in parallel
        multi_filter = await asyncio.gather(
            *(subscription_obj.parse_filters(f, logger) for f in subscription_obj.filters)
        )

        # Initialize Redis client
        redis_client = await get_redis_client()

        # Check cache in parallel
        async def check_cache(filter_set):
            cache_key = str(filter_set)
            return cache_key, await redis_client.get(cache_key)

        cache_results = await asyncio.gather(*(check_cache(f) for f in multi_filter))

        # Separate cache hits and misses
        cache_hits = [orjson.loads(res) for _, res in cache_results if res]
        cache_misses = [(key, f) for key, res, f in zip(*zip(*cache_results), multi_filter) if not res]

        # Query cache misses in the database
        async def query_database(cache_key, filter_set):
            sql_query = subscription_obj.base_query_builder(*filter_set, logger)
            query_results = await execute_sql_with_tracing(app, sql_query, "SELECT * FROM EVENTS")
            parsed_results = await subscription_obj.query_result_parser(query_results)
            await redis_client.setex(cache_key, 240, orjson.dumps(parsed_results))
            return parsed_results

        db_results = await asyncio.gather(
            *(query_database(key, f) for key, f in cache_misses)
        ) if cache_misses else []

        # Combine results
        combined_results = [result for res_list in cache_hits + db_results for result in res_list]


        await redis_client.close()  # Ensure Redis client is properly closed

        return subscription_obj.sub_response_builder(
            "EVENT", subscription_obj.subscription_id, combined_results, 200
        )
    except (psycopg.Error, Exception) as exc:
        logger.error(f"An error occurred: {exc}", exc_info=True)
        return subscription_obj.sub_response_builder(
            "EOSE", subscription_obj.subscription_id, "", 500
        )


if __name__ == "__main__":
    logger.info(f"Write conn string is: {get_conn_str('WRITE')}")
    logger.info(f"Read conn string is: {get_conn_str('READ')}")
    initialize_db(logger=logger, write_str=init_conn_str)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("EVENT_HANDLER_PORT")))
