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

load_dotenv()

options = {"statsd_host": "172.28.0.5", "statsd_port": 8125}
initialize(**options)

redis_client = redis.Redis(host="172.28.0.6", port=6379)


tracer.configure(hostname="172.28.0.5", port=8126)
redis_client: redis.Redis = redis.Redis(host="172.28.0.6", port=6379)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_file = "./logs/event_handler.log"
handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class Event:
    def __init__(
        self,
        event_id: str,
        pubkey: str,
        kind: int,
        created_at: int,
        tags: List,
        content: str,
        sig: str,
    ) -> None:
        self.event_id = event_id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.tags = tags
        self.content = content
        self.sig = sig

    def __str__(self) -> str:
        return f"{self.event_id}, {self.pubkey}, {self.kind}, {self.created_at}, {self.tags}, {self.content}, {self.sig} "


async def generate_query(tags) -> str:
    base_query = " EXISTS ( SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE {})"
    conditions = []
    for tag_pair in tags:
        condition = f"elem @> '{json.dumps(tag_pair)}'"
        conditions.append(condition)

    complete_query = base_query.format(" OR ".join(conditions))
    return complete_query


async def sanitize_event_keys(filters) -> Dict:
    try:
        try:
            filters.pop("limit")
        except:
            logger.debug(f"No limit")
        logger.debug(f"Filter variable is: {filters} and of length {len(filters)}")

        key_mappings = {
            "authors": "pubkey",
            "kinds": "kind",
            "ids": "id",
        }
        updated_keys = {}
        if len(filters) > 0:
            for key in filters:
                logger.debug(f"Key value is: {key}, {filters[key]}")
    
                new_key = key_mappings.get(key, key)
                if new_key != key:
                    stored_val = filters[key]
                    updated_keys[new_key] = stored_val
                    logger.debug(f"Adding new key {new_key} with value {stored_val}")
                else:
                    updated_keys[key] = filters[key]
    
            return updated_keys
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return updated_keys


async def parse_sanitized_query(updated_keys) -> Tuple[List, List]:
    tag_values = []
    query_parts = []
    if len(updated_keys) < 0:
        return {}, {}


    for item in updated_keys:
        outer_break = False

        if item.startswith("#"):
            logger.debug(
                f"Tag key is: {item}, value is {updated_keys[item]} and of type: {type(updated_keys[item])}"
            )

            try:
                for tags in updated_keys[item]:
                    tag_value_pair = json.dumps([item[1], tags])
                    logger.debug(f"Adding tag key value pair: {tag_value_pair}")
                    tag_values.append(tag_value_pair)
                    outer_break = True
                    continue
            except TypeError as e:
                logger.error(f"Error processing tags for key {item}: {e}")

        elif item in ["since", "until"]:
            if item == "since":
                q_part = f'created_at > {updated_keys["since"]}'
                query_parts.append(q_part)
                outer_break = True
                continue
            elif item == "until":
                q_part = f'created_at < {updated_keys["until"]}'
                query_parts.append(q_part)
                outer_break = True
                continue

        if outer_break:
            continue

        q_part = f"{item} = ANY(ARRAY {updated_keys[item]})"
        logger.debug(f"q_part is {q_part}")
        query_parts.append(q_part)

    return tag_values, query_parts


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
        event_id=event_dict.get("id", ""),
        pubkey=event_dict.get("pubkey", ""),
        kind=event_dict.get("kind", 0),
        created_at=event_dict.get("created_at", 0),
        tags=event_dict.get("tags", {}),
        content=event_dict.get("content", ""),
        sig=event_dict.get("sig", ""),
    )

    logger.debug(f"Created event object {event_obj}")

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


async def generate_query(tags) -> str:
    base_query = "EXISTS (SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE {})"
    or_conditions = " OR ".join(f"elem @> '{tag}'" for tag in tags)
    complete_query = base_query.format(or_conditions)
    return complete_query


async def parser_worker(record, column_added) -> None:
    column_names = ["id", "pubkey", "kind", "created_at", "tags", "content", "sig"]
    row_result = {}
    i = 0
    for item in record:
        row_result[column_names[i]] = item
        i += 1
    column_added.append([row_result])


async def query_result_parser(query_result) -> List:
    column_added = []
    tasks = []
    if query_result:
        for record in query_result:
            tasks.append(parser_worker(record, column_added))
    
        await asyncio.gather(*tasks)
    
        return column_added
    else:
        return None

async def fetch_data_from_cache(redis_key):
    cached_data = redis_client.get(redis_key)
    logger.debug(f"Cached data is:{cached_data} and of type: {type(cached_data)}")
    if cached_data:
        return cached_data
    else:
        return None


@app.post("/subscription")
async def handle_subscription(request: Request) -> JSONResponse:
    try:
        response = None
        payload = await request.json()
        filters = payload.get("event_dict", {})
        subscription_id = payload.get("subscription_id", "")
        logger.debug(f"Filters are {filters}")
        if filters != {}:
            updated_keys = await sanitize_event_keys(filters)
            tag_values, query_parts = await parse_sanitized_query(updated_keys)
        else:
            response = {
                          "event": "EOSE",
                          "subscription_id": subscription_id,
                          "results_json": "None",
                      }
            return JSONResponse(content=response, status_code=200)

        async with app.async_pool.connection() as conn:
            async with conn.cursor() as cur:
                run_query = False
                if len(query_parts) > 0:
                    where_clause = " AND ".join(query_parts)
                    run_query = True
                if len(tag_values) > 0:
                    tag_clause = await generate_query(tag_values)
                    where_clause = str(where_clause) + " AND " + str(tag_clause)
                    run_query = True
                sql_query = f"SELECT * FROM events WHERE {where_clause};"
                logger.debug(f"SQL query constructed: {sql_query}")

                if run_query:
                    redis_key = f"{sql_query}"

                    fetched = await fetch_data_from_cache(redis_key)
                    if fetched:
                        if fetched == "b'[]'":
                            serialized_events == None
                        cached_data_str = fetched.decode('utf-8')
                        serialized_events = json.loads(cached_data_str)
                        columnized = await query_result_parser(serialized_events)
                        serialized_events = json.dumps(columnized)
                    else:
                        query = await cur.execute(query=sql_query)
                        listed = await cur.fetchall()
    
                        logger.debug(f"Start parser")
                        parsed_results = await query_result_parser(listed)
                        serialized_events = None
                        logger.debug(f"Parsed results are: {parsed_results}")
                        if parsed_results:
                            logger.debug(f"Parsed results are: {parsed_results}")
                            serialized_events = json.dumps(parsed_results)
                            logger.debug(f"Serialized results are {serialized_events}")
                            redis_client.setex(redis_key, 240, json.dumps(listed))
                            logger.debug(f"Line after redis")
                    if len(serialized_events) < 2:
                        response = None
                    else:
                        response = {
                            "event": "EVENT",
                            "subscription_id": subscription_id,
                            "results_json": serialized_events,
                        }

    except psycopg.Error as exc:
        logger.error(f"Error occurred: {str(exc)}")
        return JSONResponse(content="None", status_code=500)

    except Exception as exc:
        logger.error(f"General exception occured: {exc}")
    finally:
        try:
            if response is None:
                response = {
                    "event": "EOSE",
                    "subscription_id": subscription_id,
                    "results_json": "None",
                }
            return JSONResponse(content=response, status_code=200)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    initialize_db()
    uvicorn.run(app, host="0.0.0.0", port=80)