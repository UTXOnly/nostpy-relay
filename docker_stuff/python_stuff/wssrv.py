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



logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

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



import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)


# Now you can use logging.debug(), logging.info(), etc. to log messages to stdout.


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
    if sig != computed_id:
        await websocket.send(json.dumps({"error": "Invalid signature"}))
        return

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
    



async def handle_subscription_request(subscription_dict, websocket):
    logger = logging.getLogger(__name__)

    subscription_id = subscription_dict.get("subscription_id")
    filters = subscription_dict.get("filters", {})
    with SessionLocal() as db:
        query = db.query(Event)
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
        if filters.get("since"):
            query = query.filter(Event.created_at > filters.get("since"))
        if filters.get("until"):
            query = query.filter(Event.created_at < filters.get("until"))
        query_result = query.limit(filters.get("limit", 100)).all()

        # Send subscription data to client
        subscription_data = {
            "subscription_id": subscription_id,
            "filters": filters,
            "query_result": query_result
        }
        logger.debug("Sending subscription data to client")
        logger.debug(subscription_data)
        await websocket.send(json.dumps({
            "subscription_id": subscription_id,
            "query_result": query_result
        }))



async def handle_websocket_connection(websocket, path):
    logger = logging.getLogger(__name__)

    try:
        async for message in websocket:
            logger.debug(f"Received message: {message}")

            try:
                message_dict = json.loads(message)
            except json.JSONDecodeError as e:
                logger.debug(f"Could not parse JSON: {e}")
                continue

            if "id" in message_dict and "pubkey" in message_dict and "content" in message_dict:
                # Handle new event
                logger.debug("Handling new event")
                await handle_new_event(message_dict, websocket)

            elif "REQ" in message_dict and "subscription_id" in message_dict:
                # Handle subscription request
                logger.debug("Handling subscription request")
                await handle_subscription_request(message_dict, websocket)

    finally:
        logger.debug("Connection closed")

    

if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
