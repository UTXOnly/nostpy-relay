import os
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


async def kind_1_query(filters):
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                query = session.query(Event)
                conditions = [
                    (filters.get("authors"), lambda x: Event.pubkey == (x)),
                    (filters.get("kinds"), lambda x: Event.kind == (x)),
                    (filters.get("#e"), lambda x: Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in x)),
                    (filters.get("#p"), lambda x: Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in x)),
                    (filters.get("#d"), lambda x: Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in x)),
                    (filters.get("since"), lambda x: Event.created_at > x),
                    (filters.get("until"), lambda x: Event.created_at < x),
                ]
                for value, condition in conditions:
                    if value:
                        query = query.filter(condition(value))
                query_result = query.limit(filters.get("limit", 100)).all()
                return query_result
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error occurred: {error_message}")
                raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
            finally:
                session.close()

async def kind_0_query(filters):
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                query = session.query(Event)
                conditions = [
                    (filters.get("authors"), lambda x: Event.pubkey == (x)),
                    (filters.get("kinds"), lambda x: Event.kind == (x))
                ]
                for value, condition in conditions:
                    if value:
                        query = query.filter(condition(value))
                query_result = query.limit(filters.get("limit", 100)).all()
                return query_result
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error occurred: {error_message}")
                raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
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
        Session = sessionmaker(bind=engine)
        session = Session()

        if filters.get("kinds") == 0:
            query = kind_0_query(filters)
        elif filters.get("kinds") == 1:
            query = kind_1_query(filters)
        try:
            redis_filters = []
            for event in query:
                serialized_event = serialize(event)
                redis_filters.append(serialized_event)
            #redis_client.set(cache_key, json.dumps(redis_filters), ex=3600)    
            logger.debug("Result saved in Redis cache")
            logger.debug(f"Data type of redis_filters: {type(redis_filters)}, Length of redis_filters variable is {len(redis_filters)}")
            
            if len(redis_filters) == 0:
                response = None #{'event': "EOSE", 'subscription_id': subscription_id, 'results_json': "None"}
                logger.debug(f"Data type of response: {type(response)}, End of stream event response: {response}")
            else:
                response = {'event': "EVENT", 'subscription_id': subscription_id, 'results_json': redis_filters}
                logger.debug(f"Data type of response: {type(response)}, Sending postgres query results: {response}")
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error occurred: {error_message}")
            raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
        finally:
            session.close()

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


