import os
import json
import logging
import inspect
import uvicorn
from ddtrace import tracer
from datadog import initialize, statsd
import redis
from sqlalchemy import create_engine, Column, String, Integer, JSON, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, class_mapper
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


options = {
    'statsd_host':'172.28.0.5',
    'statsd_port':8125
}

initialize(**options)

tracer.configure(hostname='172.28.0.5', port=8126)
redis_client = redis.Redis(host='172.28.0.6', port=6379)

logger = logging.getLogger(__name__)
logging.basicConfig(filename='./logs/event_handler.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=True)
Base = declarative_base()

class Event(Base):
    __tablename__ = 'event'

    id = Column(String, primary_key=True, index=True)
    pubkey = Column(String, index=True)
    kind = Column(Integer, index=True)
    created_at = Column(Integer, index=True)
    tags = Column(JSON)
    content = Column(String)
    sig = Column(String)

    def __init__(self, id: str, pubkey: str, kind: int, created_at: int, tags: list, content: str, sig: str):
        self.id = id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.tags = tags
        self.content = content
        self.sig = sig

logger.debug("Creating database metadata")
Base.metadata.create_all(bind=engine)
app = FastAPI()

Session = sessionmaker(bind=engine)
session = Session()

@app.post("/new_event")
async def handle_new_event(request: Request):
    event_dict = await request.json()
    pubkey, kind, created_at, tags, content, event_id, sig = (
        event_dict.get(key) for key in ["pubkey", "kind", "created_at", "tags", "content", "id", "sig"]
    )
    try:
        delete_message = None
        if kind in {0, 3}:
            delete_message = f"Deleting existing metadata for pubkey {pubkey}"
            session.query(Event).filter_by(pubkey=pubkey, kind=kind).delete()

        existing_event = session.query(Event).filter_by(id=event_id).scalar()
        if existing_event is not None:
            raise HTTPException(status_code=409, detail=f"Event with ID {event_id} already exists")

        new_event = Event(
            id=event_id,
            pubkey=pubkey,
            kind=kind,
            created_at=created_at,
            tags=tags,
            content=content,
            sig=sig
        )

        session.add(new_event)
        session.commit()
        statsd.increment('nostr.event.added.count', tags=["func:new_event"])
        message = "Event added successfully" if kind == 1 else "Event updated successfully"
        response = {"message": message}
        return JSONResponse(content=response, status_code=200)
    
    except SQLAlchemyError as e:
        logger.exception(f"Error saving event: {e}")
        raise HTTPException(status_code=500, detail="Failed to save event to database")

    finally:
        if delete_message:
            logger.debug(delete_message.format(pubkey=pubkey))


def serialize(model):
    # Helper function to convert an SQLAlchemy model instance to a dictionary
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in columns)

async def event_query(filters):
    # Set a cache key based on the filters
    serialized_events = []
    logger.debug(f"type of filters recieved is: {type(filters)}")
    results = json.loads(filters)
    logger.debug(f"Results to be queried are: {results}, of datatype: {type(results)}")
    list_index = 0
    index = 2
    logger.debug(f"event_query func results are: {(results[list_index][str(index)])}")
    output_list = []

    for result in results:
        extracted_dict = result[2]
        if isinstance(result, dict):
            output_list.append(extracted_dict)
        redis_get = str(result[2])
        logger.debug(f"Redis get is {redis_get}")
        cached_result = redis_client.get(redis_get)
        logger.debug(f"Cache key: {cached_result} ({inspect.currentframe().f_lineno})")

        if cached_result:
            # If the result exists in the cache, return it
            query_result = cached_result
            query_result_utf8 = query_result.decode('utf-8')
            query_result_cleaned = query_result_utf8.strip("[b\"")
            logger.debug(f"Query result CLEANED = {query_result_cleaned}")
            logger.debug(f"Query result found in cache. ({inspect.currentframe().f_lineno})")
            statsd.increment('nostr.event.found.redis.count', tags=["func:event_query"])
            serialized_events.append(query_result_cleaned)
            
        else:
        
            try:
                query = session.query(Event)
            
                conditions = {
                    "authors": lambda x: Event.pubkey.in_(x),
                    "kinds": lambda x: Event.kind.in_(x),
                    "#e": lambda x: Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in x),
                    "#p": lambda x: Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in x),
                    "#d": lambda x: Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in x),
                    "since": lambda x: Event.created_at > x,
                    "until": lambda x: Event.created_at < x
                }

                for index, dict_item in enumerate(output_list):
                    query_limit = int(min(dict_item.get('limit', 100), 100))
                    if 'limit' in dict_item:
                        del dict_item['limit']
                    for key, value in dict_item.items():
                        logger.debug(f"Key value is: {key}, {value}")
                        query = query.filter(conditions[key](value))
                query_result = query.order_by(desc(Event.created_at)).limit(query_limit).all()
                statsd.increment('nostr.event.queryied.postgres', tags=["func:event_query"])
                serialized_events = [serialize(event) for event in query_result]
                redis_set = redis_client.set(redis_get, str(serialized_events))  # Set cache expiry time to 2 min
                redis_client.expire(redis_get, 300)
                logger.debug(f"Query result stored in cache. Stored as: {redis_set} ({inspect.currentframe().f_lineno})")
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error occurred: {error_message} ({inspect.currentframe().f_lineno})")
            finally:
                logger.debug("FINISH PG BLOCK")
    return serialized_events

@app.post("/subscription")
async def handle_subscription(request: Request):
    try:
        response = None
        payload = await request.json()
        logger.debug(f"Payload is: {payload}", inspect.currentframe().f_lineno)
        subscription_dict = payload.get('event_dict')
        subscription_id = payload.get('subscription_id')
        filters = subscription_dict
        statsd.increment('nostr.subscription.recieved.count', tags=["func:subscription"])
        logger.debug(f"Filters are: {filters} of the type: {type(filters)} {inspect.currentframe().f_lineno}")
        serialized_events = await event_query(json.dumps(filters))#event_query(filters)
        logger.debug(f"THE QUERY IS: {serialized_events} ({inspect.currentframe().f_lineno})")
        logger.debug(f"Data type of wh_filters: {type(serialized_events)}, Length of wh_filters variable is {len(serialized_events)} ({inspect.currentframe().f_lineno})")
        if len(serialized_events) == 0:
            response = None #{'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
            logger.debug(f"Data type of response: {type(response)}, End of stream event response: {response} ({inspect.currentframe().f_lineno})")
        else:
            response = {'event': "EVENT", 'subscription_id': subscription_id, 'results_json': serialized_events}
            logger.debug(f"Data type of response: {type(response)}, Sending postgres query results: {response} ({inspect.currentframe().f_lineno})")

    except Exception as e:
        error_message = str(e)
        logger.error(f"Error occurred: {error_message} ({inspect.currentframe().f_lineno})")
        raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
    finally:
        if response is None:
            logger.debug(f"Response type is None = {response} ({inspect.currentframe().f_lineno})")
            response = {'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
        logger.debug(f"Finally block, returning JSON response to wh client {response} ({inspect.currentframe().f_lineno})")
        return JSONResponse(content=response, status_code=200)
 
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
