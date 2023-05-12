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


logger.debug("Creating database metadata")
Base.metadata.create_all(bind=engine)


app = FastAPI()


@app.post("/new_event")
def handle_new_event(request: Request):
    event_dict = request.json()
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
        response = {"message": "Event added successfully"}
        return JSONResponse(content=response, status_code=200)
    except Exception as e:
        logger.exception(f"Error saving event: {e}")
        raise HTTPException(status_code=500, detail="Failed to save event to database")
    finally:
        session.close()


def serialize(model):
    # Helper function to convert an SQLAlchemy model instance to a dictionary
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in columns)


@app.post("/subscription")
def handle_subscription(request: Request):
    try:
        payload = request.json()
        subscription_dict = payload.get('event_dict')
        subscription_id = payload.get('subscription_id')
        origin = payload.get('origin')
        filters = subscription_dict

        # Redis cache key from subscription filters
        cache_key = json.dumps(filters)
        # Check if the result is already cached
        cached_result = redis_client.get(cache_key)
        if cached_result:
            logger.debug("Result found in Redis cache")
            result = json.loads(cached_result)
            logger.debug(f"Result: {result}")

            response = {
                'result': result,
                'subscription_id': subscription_id
            }
            return JSONResponse(content=response)

        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            query = session.query(Event)
            if filters.get("ids"):
                query = query.filter(Event.id.in_(filters.get("ids")))
            if filters.get("authors"):
                query = query.filter(Event.pubkey.in_(filters.get("authors")))
            if filters.get("kinds"):
                query = query.filter(Event.kind.in_(filters.get("kinds")))
            if filters.get("#e"):
                query = query.filter(Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in filters.get("#e")))
            if filters.get("#p"):
                query = query.filter(Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in filters.get("#p")))
            if filters.get("#d"):
                query = query.filter(Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in filters.get("#d")))
            if filters.get("since"):
                query = query.filter(Event.created_at > filters.get("since"))
            if filters.get("until"):
                query = query.filter(Event.created_at < filters.get("until"))
            query_result = query.limit(filters.get("limit", 100)).all()

            redis_filters = []
            for event in query_result:
                serialized_event = serialize(event)
                redis_filters.append(serialized_event)

            response = {
                'result': redis_filters,
                'subscription_id': subscription_id
            }

            # Cache the result for future requests
            redis_client.set(cache_key, json.dumps(redis_filters), ex=3600)
            logger.debug("Result saved in Redis cache")

            return JSONResponse(content=response)

        except Exception as e:
            # Handle the exception and return an error response
            error_message = str(e)
            logger.error(f"Error occurred: {error_message}")
            raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
        finally:
            session.close()

    except Exception as e:
        # Handle the exception and return an error response
        error_message = str(e)
        logger.error(f"Error occurred: {error_message}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the subscription")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)


