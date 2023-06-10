import os
import json
import logging
import redis
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
logging.basicConfig(level=logging.DEBUG)

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

import json
import redis

# ...

redis_client = redis.Redis(host='172.28.0.6', port=6379)

async def event_query(filters):
    # Set a cache key based on the filters
    cache_key = json.dumps(filters)

    # Check if the query result exists in the Redis cache
    cached_result = redis_client.get(cache_key)

    if cached_result:
        # If the result exists in the cache, return it
        query_result = json.loads(cached_result)
    else:
        Session = sessionmaker(bind=engine)
        session = Session()
    
        try:
            query = session.query(Event)
        
            conditions = {
                "authors": lambda x: Event.pubkey == x,
                "kinds": lambda x: Event.kind.in_(x),
                "#e": lambda x: Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in x),
                "#p": lambda x: Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in x),
                "#d": lambda x: Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in x),
                "since": lambda x: Event.created_at > x,
                "until": lambda x: Event.created_at < x
            }
        
            for key, value in filters.items():
                if key in conditions and value is not None:
                    query = query.filter(conditions[key](value))
                
            limit = filters.get("limit")
            query_result = query.order_by(desc(Event.created_at)).limit(limit).all()

            # Store the query result in the Redis cache for future use
            redis_client.set(cache_key, json.dumps(query_result), ex=3600)  # Set cache expiry time to 1 hour

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error occurred: {error_message}")
            query_result = []
        finally:
            session.close()

    return query_result




@app.post("/subscription")
async def handle_subscription(request: Request):
    try:
        response = None
        payload = await request.json()
        logger.debug(payload)
        subscription_dict = payload.get('event_dict')
        subscription_id = payload.get('subscription_id')
        origin = payload.get('origin')
        filters = subscription_dict
        logger.debug(f"Filters are: {filters} of the type: {type(filter)}")

        query = await event_query(filters)
        logger.debug(f"THE QUERY IS: {query}")
        # serialize results asynchronously and gather them into a list
        serialized_events = []
        for event in query:
            serialized_event = serialize(event)
            serialized_events.append(serialized_event)
        
        # set Redis cache with all serialized events
        #redis_client.set(cache_key, json.dumps(serialized_events), ex=3600)    
        logger.debug("Result saved in Redis cache")
        logger.debug(f"Data type of redis_filters: {type(serialized_events)}, Length of redis_filters variable is {len(serialized_events)}")
        if len(serialized_events) == 0:
            response = None #{'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
            logger.debug(f"Data type of response: {type(response)}, End of stream event response: {response}")
        else:
            response = {'event': "EVENT", 'subscription_id': subscription_id, 'results_json': serialized_events}
            logger.debug(f"Data type of response: {type(response)}, Sending postgres query results: {response}")

    except Exception as e:
        error_message = str(e)
        logger.error(f"Error occurred: {error_message}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
    finally:
        if response is None:
            logger.debug(f"Response type is None = {response}")
            response = {'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
        logger.debug(f"Finally block, returning JSON response to wh client {response}")
        return JSONResponse(content=response, status_code=200)
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
