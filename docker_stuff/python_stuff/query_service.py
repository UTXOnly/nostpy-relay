import os
import asyncio
import json
import logging
import redis
from ddtrace import tracer
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker, class_mapper
from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base

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

app = FastAPI()

def serialize(model):
    # Helper function to convert an SQLAlchemy model instance to a dictionary
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in columns)

async def event_query(filters):
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        query = session.query(Event)
        
        conditions = {
            "authors": lambda x: Event.pubkey == x,
            "kinds": lambda x: Event.kind == x,
            "#e": lambda x: Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in x),
            "#p": lambda x: Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in x),
            "#d": lambda x: Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in x),
            "since": lambda x: Event.created_at > x,
            "until": lambda x: Event.created_at < x
        }
        
        for key, value in filters.items():
            if key in conditions and value is not None:
                query = query.filter(conditions[key](value))
                
        limit = filters.get("limit", 100)
        query_result = query.limit(limit).all()
        return query_result
    
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error occurred: {error_message}")
        pass
        
    finally:
        session.close()


@app.post("/subscription")
async def handle_subscription(request: Request):
    try:
        response = None
        payload = await request.json()
        subscription_dict = payload.get('event_dict')
        subscription_id = payload.get('subscription_id')
        origin = payload.get('origin')
        filters = subscription_dict

        query = await event_query(filters)
        logger.debug(f"THE QUERY IS: {query}")
        # serialize results asynchronously and gather them into a list
        serialized_events = await asyncio.gather(*(serialize(event) for event in query))
        
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


