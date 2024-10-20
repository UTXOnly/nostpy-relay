import copy
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Iterable, Callable, Dict, List

import psycopg
import redis
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.metrics import Observation
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.trace import SpanAttributes
from otel_metric_base.otel_metrics import OtelMetricBase
from psycopg_pool import AsyncConnectionPool

from event_classes import Event, Subscription
from init_db import initialize_db

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


WOT_ENABLED = os.getenv("WOT_ENABLED")

app = FastAPI()

# Set up logging
logger_provider = LoggerProvider(
    resource=Resource.create({"service.name": "event_handler_otel"})
)
set_logger_provider(logger_provider)

log_exporter = OTLPLogExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"), insecure=True
)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

handler = LoggingHandler(
    level=logging.DEBUG,
    logger_provider=logger_provider,
)

# Create a single logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": "event_handler_otel"}))
)
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
span_processor = BatchSpanProcessor(otlp_exporter)
otlp_tracer = trace.get_tracer_provider().add_span_processor(span_processor)


# Set up a separate tracer provider for Redis
redis_tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": "redis"})
)
redis_tracer = redis_tracer_provider.get_tracer(__name__)

# Set up the OTLP exporter and span processor for Redis
redis_otlp_exporter = OTLPSpanExporter()
redis_span_processor = BatchSpanProcessor(redis_otlp_exporter)
redis_tracer_provider.add_span_processor(redis_span_processor)

# Instrument Redis with the separate tracer provider
RedisInstrumentor().instrument(tracer_provider=redis_tracer_provider)
redis_client = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"))


wot_metric_counter: Dict[str, Dict] = {}
added_metric_counter: Dict[str, Dict] = {}
query_metric_counter: Dict[str, Dict] = {}


# Function to increment counters with tags
def increment_counter(tags: Dict[str, str], counter_dict):
    tag_key = str(sorted(tags.items()))  # Convert dict to a unique key
    if tag_key in counter_dict:
        counter_dict[tag_key]["count"] += 1
    else:
        counter_dict[tag_key] = {"count": 1, "tags": tags}


# Create an observable callback to generate metrics based on current counter values
def create_observable_callback(counter_dict) -> Callable:
    def observable_callback(_):
        return [
            Observation(entry["count"], entry["tags"])
            for entry in counter_dict.values()
        ]

    return observable_callback


# Initialize OtelMetrics
otel_metrics = OtelMetricBase(otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))

# Register observable metrics with callbacks (all use the same callback)
otel_metrics.meter.create_observable_counter(
    name="wot_event_reject",
    description="Rejected note from WoT filter",
    callbacks=[create_observable_callback(wot_metric_counter)],
)

otel_metrics.meter.create_observable_counter(
    name="event_added",
    description="Event added",
    callbacks=[create_observable_callback(added_metric_counter)],
)

otel_metrics.meter.create_observable_counter(
    name="event_query",
    description="Event query",
    callbacks=[create_observable_callback(query_metric_counter)],
)


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

    app.write_pool = AsyncConnectionPool(conninfo=conn_str_write)
    app.read_pool = AsyncConnectionPool(conninfo=conn_str_read)

    yield

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


@app.post("/new_event")
async def handle_new_event(request: Request) -> JSONResponse:
    event_dict = await request.json()
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
        f"New event loop iter, ev object is {event_obj.event_id} and {event_obj.kind}"
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
                    otel_tags = {"kind": event_obj.kind, "pubkey": event_obj.pubkey}
                    if WOT_ENABLED in ["True", "true"]:
                        wot_check = await event_obj.check_wot(cur)
                        if not wot_check:
                            logger.debug(f"allow check failed: {wot_check}")

                            increment_counter(otel_tags, wot_metric_counter)
                            return event_obj.evt_response(
                                results_status="false",
                                http_status_code=403,
                                message="rejected: user is not in relay's web of trust",
                            )

                    if event_obj.kind in [0, 3]:
                        await event_obj.delete_check(conn, cur)
                        logger.debug(f"Adding event id: {event_obj.event_id}")
                        await event_obj.add_event(conn, cur)
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
                            wot_metric_counter: Dict[str, Dict] = {}
                            increment_counter(otel_tags, added_metric_counter)
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

                    return event_obj.evt_response(
                        results_status="true", http_status_code=200
                    )
    except Exception as exc:
        logger.debug(f"Entering general exception: {exc}")
        await conn.rollback()
        return event_obj.evt_response(
            results_status="false",
            http_status_code=500,
            message="error: could not connect to the database",
        )


@app.post("/subscription")
async def handle_subscription(request: Request) -> JSONResponse:
    try:
        request_payload = await request.json()
        subscription_obj = Subscription(request_payload)

        if not subscription_obj.filters:
            return subscription_obj.sub_response_builder(
                "EOSE", subscription_obj.subscription_id, "", 204
            )
        raw_filters_copy = copy.deepcopy(subscription_obj.filters)
        (
            tag_values,
            query_parts,
            limit,
            global_search,
        ) = await subscription_obj.parse_filters(subscription_obj.filters, logger)

        query_tags = {"env": "pre-cache"}
        increment_counter(query_tags, query_metric_counter)

        cached_results = subscription_obj.fetch_data_from_cache(
            str(raw_filters_copy), redis_client
        )
        logger.debug(f"Cached results are {cached_results}")

        sql_query = subscription_obj.base_query_builder(
            tag_values, query_parts, limit, global_search, logger
        )

        if cached_results is None:
            query_results = await execute_sql_with_tracing(
                app, sql_query, "SELECT * FROM EVENTS"
            )
            if query_results:
                parsed_results = await subscription_obj.query_result_parser(
                    query_results
                )
                serialized_events = json.dumps(parsed_results)
                redis_client.setex(str(raw_filters_copy), 240, serialized_events)
                logger.debug(
                    f"Caching results, keys: {str(raw_filters_copy)} value is: {serialized_events}"
                )
                return subscription_obj.sub_response_builder(
                    "EVENT", subscription_obj.subscription_id, serialized_events, 200
                )
            else:
                redis_client.setex(str(raw_filters_copy), 240, "")
                return subscription_obj.sub_response_builder(
                    "EOSE", subscription_obj.subscription_id, "", 200
                )
    except psycopg.Error as exc:
        logger.error(f"Error occurred: {str(exc)}", exc_info=True)
        return subscription_obj.sub_response_builder(
            "EOSE", subscription_obj.subscription_id, "", 500
        )
    except Exception as exc:
        logger.error(f"General exception occurred: {exc}", exc_info=True)
        return subscription_obj.sub_response_builder(
            "EOSE", subscription_obj.subscription_id, "", 500
        )


if __name__ == "__main__":
    logger.info(f"Write conn string is: {get_conn_str('WRITE')}")
    logger.info(f"Read conn string is: {get_conn_str('READ')}")
    initialize_db(logger=logger, write_str=init_conn_str)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("EVENT_HANDLER_PORT")))
