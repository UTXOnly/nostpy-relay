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



async def handle_websocket_connection(websocket, path):
    """
    Handler function for WebSocket connections.
    """
    logger = logging.getLogger(__name__)
    logger.debug("New websocket connection established")
    async for message in websocket:
        message_list = json.loads(message)
        logger.debug(f"Received message: {message_list}")

        # Check if the incoming message is an event or request containing a query dictionary
        if len(message_list) == 3 and isinstance(message_list[1], str) and isinstance(message_list[2], dict):
            try:
                message_type = message_list[0]
                request_id = message_list[1]
                query_dict = message_list[2]

                # Handle different types of messages based on their structure
                if message_type == "EVENT":
                    # Call `handle_new_event` function with event dictionary
                    await handle_new_event(query_dict)
                elif message_type == "REQUEST":
                    # Call `handle_query_event` function with query dictionary and send the response back to client
                    filters = query_dict.get("filters", {})
                    await handle_query_event(filters, websocket, request_id)
                elif "SUBSCRIBE" in query_dict:
                    # Handle subscription-related requests
                    logger.warning("Subscription-related requests are not implemented")
                else:
                    logger.warning(f"Unsupported message format: {query_dict}")
            except Exception as e:
                logger.exception(f"Error handling {message_type}: {e}")
                await websocket.send(json.dumps({"error": str(e)}))
        else:
            logger.warning(f"Unsupported message format: {message_list}")






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
