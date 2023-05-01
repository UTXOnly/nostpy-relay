import os
import json
import asyncio
import websockets
import hmac
import hashlib
from time import time
from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


logging.basicConfig(level=logging.DEBUG)
# Add debug log lines to show DATABASE_URL value
DATABASE_URL = os.environ.get("DATABASE_URL")
logger.debug(f"DATABASE_URL value: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    
    @classmethod
    def add_event_to_database(cls, event_data):
        with SessionLocal() as session:
            new_event = cls(**event_data)
            logging.debug(f'created new event:\n{new_event}')
            session.add(new_event)
            logging.debug('about to commit session changes...')
            session.commit()

            # log confirmation message
            logging.info(f"Added event {new_event.id} to database.")


# Add debug log line to show metadata creation
logger.debug("Creating database metadata")
Base.metadata.create_all(bind=engine)
def test_send_event():
    # assuming you've already set up the necessary imports and logging configs

    # create test event data
    event_data = {
        'id': '528330f3aa49b00e8aec29213b2da88e547b293b3721e95c2245b26ffecdb747',
        'pubkey': '0f0b173aee28fa4d4e8868e51b2cd5c8743f37c0a8584b7cb06c880d52a397c5',
        'content': 'bvcbvcbvc',
        'kind': 1,
        'created_at': 1682904563,
        'tags': [],
        'sig': 'ac0ae0551ffeafb3a2ea04ec2d5a1675cc122c2f5763c7890f7d0cbced00b2fbf584413081a5fc152c9845c8643ec90e9e4433ce2dbf1fb6d257998ed3d80427'
    }

    # send event
    logging.debug(f'Sending event: {event_data}')
    Event.add_event_to_database(event_data)

    # log confirmation message
    logging.debug('Event sent successfully.')

test_data = test_send_event()


async def handle_new_event(event_dict, websocket):
    logger = logging.getLogger(__name__)
    pubkey = event_dict.get("pubkey")
    kind = event_dict.get("kind")
    created_at = event_dict.get("created_at")
    tags = event_dict.get("tags")
    content = event_dict.get("content")
    event_id = event_dict.get("id")
    sig = event_dict.get("sig")

    # Compute ID from event data and check signature
    event_data = json.dumps([0, pubkey, created_at, kind, tags, content], sort_keys=True)
    computed_id = hashlib.sha256(event_data.encode()).hexdigest()
    #if sig != computed_id:
    #    await websocket.send(json.dumps({"error": "Invalid signature"}))
    #    return
#
    # Save event to database
    try:
        with SessionLocal() as db:
            new_event = Event(
                id=event_id,
                pubkey=pubkey,
                kind=kind,
                created_at=created_at,
                tags=tags,
                content=content,
                sig=sig
            )
            db.add(new_event)
            db.commit()
    except Exception as e:
        logging.exception(f"Error saving event: {e}")
        await websocket.send(json.dumps({"error": "Failed to save event to database"}))
    else:
        logging.debug("Event received and processed")
        await websocket.send(json.dumps({"message": "Event received and processed"}))

async def handle_subscription_request(req_type, sub_id, event_dict, websocket):
    if req_type == "SUBSCRIBE":
        # Subscribe to events with matching tags
        tags = event_dict.get("tags")
        # TODO: Implement subscription logic
        await websocket.send(json.dumps({"message": f"Subscribed to events with tags {tags}"}))
    elif req_type == "UNSUBSCRIBE":
        # Unsubscribe from events with matching tags
        tags = event_dict.get("tags")
        # TODO: Implement unsubscription logic
        await websocket.send(json.dumps({"message": f"Unsubscribed from events with tags {tags}"}))
    else:
        await websocket.send(json.dumps({"error": f"Invalid request type {req_type}"}))

async def handle_websocket_connection(websocket, path):
    logger = logging.getLogger(__name__)
    logger.debug("New websocket connection established")
    async for message in websocket:
        message_list = json.loads(message)
        logger.debug(f"Received message: {message_list}")
        
        if len(message_list) == 2 and message_list[0] == "EVENT":
            # Extract event information from message
            event_dict = message_list[1]
            await handle_new_event(event_dict, websocket)
        elif len(message_list) == 2 and message_list[0] == "REQ":
            # Extract subscription information from message
            request_dict = message_list[1]
            subscription_id = request_dict.get("subscription_id")
            filters = request_dict.get("filters", {})

            # Determine which subscription function to call based on the presence of a "query" key in the filters
            if filters.get("query"):
                await handle_subscription_request(request_dict, websocket)
            else:
                req_type = request_dict.get("REQ")
                event_dict = request_dict.get("event_dict")
                await handle_subscription_request(req_type, subscription_id, event_dict, websocket)
        else:
            logger.warning(f"Unsupported message format: {message_list}")



#async def handle_subscription_request(subscription_dict, websocket):
#    logger = logging.getLogger(__name__)
#
#    subscription_id = subscription_dict.get("subscription_id")
#    filters = subscription_dict.get("filters", {})
#    with SessionLocal() as db:
#        query = db.query(Event)
#
#        # Construct query based on channel and filters
#        if subscription_id.startswith("timeline:"):
#            channel, subchannel = subscription_id.split(":")[1:]
#            if subchannel == "all":
#                query = query.filter(Event.kind.in_(filters.get("kinds", [])))
#            elif subchannel == "latest":
#                query = query.filter(Event.kind.in_(filters.get("kinds", [])))
#                query = query.limit(filters.get("limit", 100))
#                query = query.order_by(Event.created_at.desc())
#            else:
#                raise ValueError("Unsupported subchannel for timeline channel")
#        elif subscription_id.startswith("login:"):
#            channel, user_id = subscription_id.split(":")[1:]
#            if channel == "lists":
#                query = query.filter(Event.pubkey.in_(filters["authors"]))
#                query = query.filter(Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in filters.get("#p", [])))
#                query = query.filter(Event.kind.in_([3, 4, 5]))
#                query = query.limit(20)
#                query = query.order_by(Event.created_at.desc())
#            else:
#                raise ValueError("Unsupported channel for login")
#
#        query_result = query.all()
#
#        # Send subscription data to client
#        subscription_data = {
#            "subscription_id": subscription_id,
#            "filters": filters,
#            "query_result": query_result
#        }
#        logger.debug("Sending subscription data to client")
#        logger.debug(subscription_data)
#        await websocket.send(json.dumps({
#            "subscription_id": subscription_id,
#            "query_result": query_result
#        }))

async def handle_query_event(query_dict, websocket):
    logger = logging.getLogger(__name__)
    
    # Extract query information from request
    pubkey = query_dict.get("pubkey")
    kind = query_dict.get("kind")
    created_at = query_dict.get("created_at")
    tags = query_dict.get("tags")

    # Build query based on provided parameters
    query = {}
    if pubkey:
        query['pubkey'] = pubkey
    if kind:
        query['kind'] = kind
    if created_at:
        query['created_at'] = created_at
    if tags:
        query['tags'] = {'$all': tags}

    # Search database using query
    try:
        with SessionLocal() as db:
            results = db.query(Event).filter_by(**query).all()
    except Exception as e:
        logging.exception(f"Error retrieving events: {e}")
        await websocket.send(json.dumps({"error": "Failed to retrieve events from database"}))
    else:
        logging.debug(f"{len(results)} events retrieved")
        await websocket.send(json.dumps({"message": f"{len(results)} events retrieved", "results": [event.as_dict() for event in results]}))



if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
