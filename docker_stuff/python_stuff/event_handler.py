import os
import json
import logging
from logging.handlers import RotatingFileHandler
import inspect
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv


import uvicorn
from ddtrace import tracer
from datadog import initialize, statsd
import redis
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager
import psycopg

from psycopg_pool import AsyncConnectionPool

load_dotenv()

options: Dict[str, Any] = {
    'statsd_host': '172.28.0.5',
    'statsd_port': 8125
}

initialize(**options)

tracer.configure(hostname='172.28.0.5', port=8126)
redis_client: redis.Redis = redis.Redis(host='172.28.0.6', port=6379)

logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file: str = './logs/event_handler.log'
handler: RotatingFileHandler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class Event():

    def __init__(self, event_id: str, pubkey: str, kind: int, created_at: int, tags: List, content: str, sig: str) -> None:
        self.event_id = event_id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.tags = tags
        self.content = content
        self.sig = sig

    def __str__(self) -> str:
        return f"{self.event_id}, {self.pubkey}, {self.kind}, {self.created_at}, {self.tags}, {self.content}, {self.sig} "



def get_conn_str():
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

def initialize_db():
    """
    Initialize the database by creating the necessary table if it doesn't exist.
    """
    try:
        # Replace 'your_dsn_here' with your actual DSN or connection details
        conn = psycopg.connect(get_conn_str())
        
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id VARCHAR(255) PRIMARY KEY,
                    pubkey VARCHAR(255),
                    kind VARCHAR(255),
                    created_at VARCHAR(255),
                    tags JSONB,
                    content TEXT,
                    sig VARCHAR(255)
                );
            """)
            conn.commit()
        print("Database initialization complete.")
    except psycopg.Error as caught_error:
        print(f"Error occurred during database initialization: {caught_error}")
    finally:
        conn.close()


@app.post("/dogs")
async def insert_dog(request: Request):
    try:
        async with request.app.async_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                        INSERT INTO dogs (name,age,colour)
                        VALUES (%s, %s, %s); 
                    """, ("bonzo", 10, "red",))
                await conn.commit()
    except Exception:
        await conn.rollback()

@app.post("/new_event")
async def handle_new_event(request: Request) -> JSONResponse:
    event_dict: Dict[str, Any] = await request.json()
    event_obj = Event(
    event_id=event_dict.get("id", ""),
    pubkey=event_dict.get("pubkey", ""),
    kind=event_dict.get("kind", 0),
    created_at=event_dict.get("created_at", 0),
    tags=event_dict.get("tags", {}),
    content=event_dict.get("content", ""),
    sig=event_dict.get("sig", "")
    )

    logger.debug(f"Created event object {event_obj}")


    try:
        delete_message: Optional[str] = None
        async with request.app.async_pool.connection() as conn:
            async with conn.cursor() as cur:
                if event_obj.kind in {0, 3}:
                    delete_message = f"Deleting existing metadata for pubkey {event_obj.pubkey}"
    
                    delete_query = """
                    DELETE FROM events
                    WHERE pubkey = %s AND kind = %s;
                    """
    
                    await cur.execute(delete_query, (event_obj.pubkey, event_obj.kind))
    
                    statsd.decrement('nostr.event.added.count', tags=["func:new_event"])
                    statsd.increment('nostr.event.deleted.count', tags=["func:new_event"])
    
                    await conn.commit()
                await cur.execute("""
            INSERT INTO events (event_id,pubkey,kind,created_at,tags,content,sig) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (event_obj.event_id, event_obj.pubkey, event_obj.kind, event_obj.created_at, json.dumps(event_obj.tags)
, event_obj.content, event_obj.sig))  # Add other event fields here
                await conn.commit()
        response = {'event': "OK", 'subscription_id': "n0stafarian419", 'results_json': "true"}
        statsd.increment('nostr.event.added.count', tags=["func:new_event"])
        return JSONResponse(content=response, status_code=200)

    except psycopg.IntegrityError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=f"Event with ID {event_obj.event_id} already exists") from e
    except Exception as e:
        conn.rollback() 
        raise HTTPException(status_code=409, detail=f"Error occured adding event {event_obj.event_id}") from e
    finally:
        if delete_message:
            logger.debug(delete_message.format(pubkey=event_obj.pubkey))


async def generate_query(tags):
    base_query = """
SELECT * 
FROM events 
WHERE EXISTS (
    SELECT 1 
    FROM jsonb_array_elements(tags) as elem
    WHERE {}
);
"""
    conditions = []
    for tag in tags:

        condition = f"elem @> '{tag}'"
        logger.debug(f"Condition iter is {condition}")
        conditions.append(condition)

    or_conditions = ' OR '.join(conditions)
    complete_query = base_query.format(or_conditions)
    return complete_query



@app.post("/subscription")
async def handle_subscription(request: Request) -> JSONResponse:
    try:
        response: Optional[Dict[str, Any]] = None
        payload: Dict[str, Any] = await request.json()
        subscription_dict: Dict[str, Any] = payload.get('event_dict', {})
        subscription_id: str = payload.get('subscription_id', "")
        filters: str = json.dumps(subscription_dict)
        


    #except Exception:
    #    raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
    #finally:
    #    try:
    #        if response is None:
    #            response = {'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
    #        return JSONResponse(content=response, status_code=200)
    #    except Exception as e:
    #        return JSONResponse(content={'error': str(e)}, status_code=500)
        

    #try:

        results: List[Dict[str, Any]] = json.loads(filters)
        logger.debug(f"Filter variable is: {filters}")
        list_index: int = 0
        index: int = 2
        output_list: List[Dict[str, Any]] = []

        for request in results:
            extracted_dict: Dict[str, Any] = results[list_index][str(index)]
            logger.debug(f"Extracted Dictionary is: {extracted_dict}")
            if isinstance(filters, dict):
                output_list.append(extracted_dict)
                logger.debug(f"Results variable is: {request}")
            #redis_get: str = str(results[list_index][str(index)])
        
        #conditions: Dict[str, Any] = {
        #    "authors": lambda x: Event.pubkey.in_(x),
        #    "kinds": lambda x: Event.kind.in_(x),
        #    "#e": lambda x: Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in x),
        #    "#p": lambda x: Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in x),
        #    "#d": lambda x: Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in x), 
        #    "since": lambda x: Event.created_at > x,
        #    "until": lambda x: Event.created_at < x
        #}
        tag_values = []
        for index, dict_item in enumerate(output_list):
            query_limit: int = int(min(dict_item.get('limit', 100), 100))
            if 'limit' in dict_item:
                del dict_item['limit']
            for key, value in dict_item.items():
                logger.debug(f"Key value is: {key}, {value}")
                if key in ["#e", "#p", "#d"]:
                    logger.debug(f"Tag key is : {key} , value is {value} and of type: {type(value)}")
                    
                    for tags in value:
                        logger.debug(f"Tags is {tags}")
                        value = [key[1], tags]
                        logger.debug(f"Valuevar is {value} of type: {type(value)}")
                        tag_values.append()
        logger.debug(f"Tag values are: {tag_values}")
                    
                
        completed = generate_query(tag_values)
        logger.debug(f"Completed var is : {str(completed)}")
        async with app.async_pool.connection() as conn:
            async with conn.cursor() as cur:
                logger.debug(f"Inside 2nd async context manager")
                list_all = await cur.execute("SELECT * FROM events;").fetchall()
                logger.debug(f"Log line after select all")
                listed = str(await cur.fetchall())
                query_results = await cur.execute(completed)
                qr_result = str(await cur.fetchall())
                logger.debug(f"Full table results are {list_all}")
                logger.debug(f"query results are: {qr_result}")

        #return query_results
    
                serialized_events: List[Dict[str, Any]] = await cur.execute(completed).fetchall() #await event_query(json.dumps(filters), request)

                if len(serialized_events) < 2:
                    response = None
                else:
                    response = {'event': "EVENT", 'subscription_id': subscription_id, 'results_json': serialized_events}
                

    except psycopg.Error as exc:
        
        logger.error(f"Error occurred: {str(exc)} ({inspect.currentframe().f_lineno})")

    except Exception as exc:
        logger.error(f"General exception occured: {exc}")
        
        
    finally:
        try:
            if response is None:
                response = {'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
            return JSONResponse(content=response, status_code=200)
        except Exception as e:
            return JSONResponse(content={'error': str(e)}, status_code=500)
        #logger.debug("FINISH PG BLOCK")

if __name__ == "__main__":
    initialize_db()
    uvicorn.run(app, host="0.0.0.0", port=80)

