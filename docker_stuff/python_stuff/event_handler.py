import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from typing import List, Tuple, Dict

from datadog import initialize, statsd
from ddtrace import tracer
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import psycopg
import redis
import uvicorn
from psycopg_pool import AsyncConnectionPool
from event_classes import Event, Subscription

load_dotenv()

options = {"statsd_host": "172.28.0.5", "statsd_port": 8125}
initialize(**options)

redis_client = redis.Redis(host="172.28.0.6", port=6379)


tracer.configure(hostname="172.28.0.5", port=8126)
redis_client: redis.Redis = redis.Redis(host="172.28.0.6", port=6379)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log_file = "./logs/event_handler.log"
handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def get_conn_str() -> str:
    return f"""
    dbname={os.getenv('PGDATABASE')}
    user={os.getenv('PGUSER')}
    password={os.getenv('PGPASSWORD')}
    host={os.getenv('PGHOST')}
    port={os.getenv('PGPORT')}
    """


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.async_pool = AsyncConnectionPool(conninfo=get_conn_str())
    yield
    await app.async_pool.close()


app = FastAPI(lifespan=lifespan)


def initialize_db() -> None:
    """
    Initialize the database by creating the necessary table if it doesn't exist,
    and creating indexes on the pubkey and kind columns.

    """
    try:
        conn = psycopg.connect(get_conn_str())
        with conn.cursor() as cur:
            # Create events table if it doesn't already exist
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR(255) PRIMARY KEY,
                    pubkey VARCHAR(255),
                    kind INTEGER,
                    created_at INTEGER,
                    tags JSONB,
                    content TEXT,
                    sig VARCHAR(255)
                );
            """
            )

            index_columns = ["pubkey", "kind"]
            for column in index_columns:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{str(column)}
                    ON events ({str(column)});
                """
                )

            conn.commit()
        logger.info("Database initialization complete.")
    except psycopg.Error as caught_error:
        logger.info(f"Error occurred during database initialization: {caught_error}")
        return False


@app.post("/new_event")
async def handle_new_event(request: Request) -> JSONResponse:
    event_dict = await request.json()
    event_obj = Event(
        event_id=event_dict['id'],
        pubkey=event_dict['pubkey'],
        kind=event_dict['kind'],
        created_at=event_dict['created_at'],
        tags=event_dict['tags'],
        content=event_dict['content'],
        sig=event_dict.get['sig'],
    )

    try:
        delete_message = None
        async with request.app.async_pool.connection() as conn:
            async with conn.cursor() as cur:
                if event_obj.kind in {0, 3}:
                    delete_message = (
                        f"Deleting existing metadata for pubkey {event_obj.pubkey}"
                    )

                    delete_query = """
                    DELETE FROM events
                    WHERE pubkey = %s AND kind = %s;
                    """

                    await cur.execute(delete_query, (event_obj.pubkey, event_obj.kind))

                    statsd.decrement("nostr.event.added.count", tags=["func:new_event"])
                    statsd.increment(
                        "nostr.event.deleted.count", tags=["func:new_event"]
                    )

                    await conn.commit()
                await cur.execute(
                    """
            INSERT INTO events (id,pubkey,kind,created_at,tags,content,sig) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
                    (
                        event_obj.event_id,
                        event_obj.pubkey,
                        event_obj.kind,
                        event_obj.created_at,
                        json.dumps(event_obj.tags),
                        event_obj.content,
                        event_obj.sig,
                    ),
                )
                await conn.commit()
        response = {
            "event": "OK",
            "subscription_id": "n0stafarian419",
            "results_json": "true",
        }
        statsd.increment("nostr.event.added.count", tags=["func:new_event"])
        return JSONResponse(content=response, status_code=200)

    except psycopg.IntegrityError as e:
        conn.rollback()
        raise HTTPException(
            status_code=409, detail=f"Event with ID {event_obj.event_id} already exists"
        ) from e
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=409, detail=f"Error occured adding event {event_obj.event_id}"
        ) from e

    finally:
        if delete_message:
            logger.debug(delete_message.format(pubkey=event_obj.pubkey))


@app.post("/subscription")
async def handle_subscription(request: Request) -> JSONResponse:
    try:
        request_payload = await request.json()
        subscription_obj = Subscription(request_payload)

        if not subscription_obj.filters:
            return JSONResponse(
                content={
                    "event": "EOSE",
                    "subscription_id": subscription_obj.subscription_id,
                    "results_json": "None",
                },
                status_code=204,
            )

        tag_values, query_parts = await subscription_obj.parse_filters(subscription_obj.filters)
        where_clause = " AND ".join(query_parts)

        if tag_values:
            tag_clause = await subscription_obj.generate_query(tag_values)
            where_clause += f" AND {tag_clause}"

        sql_query = f"SELECT * FROM events WHERE {where_clause} LIMIT 100;"
        logger.debug(f"SQL query constructed: {sql_query}")

        redis_key = f"{subscription_obj.filters}"
        cached_results = await subscription_obj.fetch_data_from_cache(redis_key)

        if cached_results is None:
            async with app.async_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query=sql_query)
                    listed = await cur.fetchall()
                    if listed:
                        parsed_results = await subscription_obj.query_result_parser(listed)
                        serialized_events = json.dumps(parsed_results)

                        redis_client.setex(redis_key, 240, serialized_events)
                        return JSONResponse(
                            content={
                                "event": "EVENT",
                                "subscription_id": subscription_obj.subscription_id,
                                "results_json": serialized_events,
                            },
                            status_code=200,
                        )
                    else:
                        JSONResponse(
                            content={
                                "event": "EOSE",
                                "subscription_id": subscription_obj.subscription_id,
                                "results_json": None,
                            },
                            status_code=200,
                        )

        elif cached_results:
            event_type = "EVENT"
            parse_var = json.loads(cached_results.decode("utf-8"))
            logger.debug(f" parsed var is : {parse_var}")
            results_json = json.dumps(parse_var)
            logger.debug(f"parse_var var is {parse_var} and of type {type(parse_var)}")
            if not parse_var:
                event_type = "EOSE"
                results_json = None
            return JSONResponse(
                content={
                    "event": event_type,
                    "subscription_id": subscription_obj.subscription_id,
                    "results_json": results_json,
                },
                status_code=200,
            )
        else:
            return JSONResponse(
                content={
                    "event": "EOSE",
                    "subscription_id": subscription_obj.subscription_id,
                    "results_json": "None",
                },
                status_code=200,
            )

    except psycopg.Error as exc:
        logger.error(f"Error occurred: {str(exc)}", exc_info=True)
        return JSONResponse(content="None", status_code=500)

    except Exception as exc:
        logger.error(f"General exception occurred: {exc}", exc_info=True)
        return JSONResponse(content={"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    initialize_db()
    uvicorn.run(app, host="0.0.0.0", port=80)
