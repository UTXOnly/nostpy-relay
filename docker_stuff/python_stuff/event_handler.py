import os
import json
import logging
import redis
import inspect
from ddtrace import tracer
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker, class_mapper
from sqlalchemy import create_engine, Column, String, Integer, JSON, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError


tracer.configure(hostname='172.28.0.5', port=8126)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename='./logs/event_handler.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


DATABASE_URL = os.environ.get("DATABASE_URL")
logger.debug(f"DATABASE_URL value: {DATABASE_URL}")

redis_client = redis.Redis(host='172.28.0.6', port=6379)

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

@app.post("/new_event")
async def handle_new_event(request: Request):
    event_dict = await request.json()
    pubkey = event_dict.get("pubkey")
    kind = event_dict.get("kind")
    created_at = event_dict.get("created_at")
    tags = event_dict.get("tags")
    content = event_dict.get("content")
    event_id = event_dict.get("id")
    sig = event_dict.get("sig")

    Session = sessionmaker(bind=engine)
    session = Session()

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
        
        message = "Event added successfully" if kind == 1 else "Event updated successfully"
        response = {"message": message}
        return JSONResponse(content=response, status_code=200)
    
    except SQLAlchemyError as e:
        logger.exception(f"Error saving event: {e}")
        raise HTTPException(status_code=500, detail="Failed to save event to database")

    finally:
        if delete_message:
            logger.debug(delete_message.format(pubkey=pubkey))
        session.close()

def serialize(model):
    # Helper function to convert an SQLAlchemy model instance to a dictionary
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in columns)

redis_client = redis.Redis(host='172.28.0.6', port=6379)

async def event_query(filters):
    # Set a cache key based on the filters
    serialized_events = []
    logger.debug(f"type of filters recieved is: {type(filters)}")
    results = json.loads(filters)
    logger.debug(f"Results to be quired are: {results}, of datatype: {type(results)}")
    list_index = 0
    index = 2
    logger.debug(f"event_query func results are: {(results[list_index][str(index)])}")
    output_list = []
    for request in results:
        logger.debug(f"request in result is: {(results[list_index][str(index)])} ")
        extracted_dict = results[list_index][str(index)]
        if isinstance(request, dict):
            output_list.append(extracted_dict)
        redis_get = str(results[list_index][str(index)])
        logger.debug(f"Redis get is {redis_get} ")
        cached_result = redis_client.get(redis_get)
        index += 1
        list_index += 1
        logger.debug(f"Cache key: {cached_result} ({inspect.currentframe().f_lineno})")

        logger.debug(f"Output list is: {output_list} and length is: {len(output_list)}")
    # Check if the query result exists in the Redis cache
    #cached_result = redis_client.get(cache_key)
        if cached_result:
            # If the result exists in the cache, return it
            query_result = cached_result # json.loads(cached_result)
            query_result_utf8 = query_result.decode('utf-8')
            query_result_cleaned = query_result_utf8.strip("[b\"")
            logger.debug(f"Query result CLEANED = {query_result_cleaned}")
            logger.debug(f"Query result found in cache. ({inspect.currentframe().f_lineno})")
            serialized_events.append(query_result_cleaned)
            
        else:
            Session = sessionmaker(bind=engine)
            session = Session()
        
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
                    #limit_var = dict_item['limit']
                    del dict_item['limit']
                    for key, value in dict_item.items():
                        logger.debug(f"Key value is: {key}, {value}")
                        query = query.filter(conditions[key](value))
                logger.debug(f"for loop working {query}")
                query_result = query.order_by(desc(Event.created_at)).limit(10).all()
                serialized_events = []
                for event in query_result:
                    serialized_event = serialize(event)
                    serialized_events.append(serialized_event)
    
                redis_set = redis_client.set(redis_get, str(serialized_events), ex=3600)  # Set cache expiry time to 1 hour
                logger.debug(f"Query result stored in cache. Stored as: {redis_set} ({inspect.currentframe().f_lineno})")
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error occurred: {error_message} ({inspect.currentframe().f_lineno})")
                query_result = []
            finally:
                session.close()

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
