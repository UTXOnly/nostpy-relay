import os
import json
import asyncio
import websockets
import logging
from sqlalchemy.orm import class_mapper, sessionmaker
from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

DATABASE_URL = os.environ.get("DATABASE_URL")
logger.debug(f"DATABASE_URL value: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
logger.debug("Creating database metadata")
Base.metadata.create_all(bind=engine)

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
            logger.debug(f'created new event:\n{new_event}')
            session.add(new_event)
            logger.debug('about to commit session changes...')
            session.commit()
            logger.info(f"Added event {new_event.id} to database.")

async def handle_new_event(event_dict, websocket):
    pubkey = event_dict.get("pubkey")
    kind = event_dict.get("kind")
    created_at = event_dict.get("created_at")
    tags = event_dict.get("tags")
    content = event_dict.get("content")
    event_id = event_dict.get("id")
    sig = event_dict.get("sig")

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
        logger.exception(f"Error saving event: {e}")
        await websocket.send(json.dumps({"error": "Failed to save event to database"}))
    else:
        logger.debug("Event received and processed")
        await websocket.send(json.dumps({"message": "Event received and processed"}))

async def handle_websocket_connection(websocket, path):
    headers = websocket.request_headers
    referer = headers.get("referer") #Snort
    origin = headers.get("origin")
    logger.debug(f"New websocket connection established from URL: {referer or origin}")

    if headers.get("Accept") == "application/nostr+json":
        response = {
            "name": "wss://nostpy.io",
            "description": "NostPy relay v0.1",
            "pubkey": "4503baa127bdfd0b054384dc5ba82cb0e2a8367cbdb0629179f00db1a34caacc",
            "contact": "bh419@protonmail.com",
            "supported_nips": [1, 2, 4, 15, 16, 25],
            "software": "git+https://github.com/UTXOnly/nost-py.git",
            "version": "0.1"
        }
        response_json = json.dumps(response)
        logger.debug(f"Sending JSON response: {response_json}")
        await websocket.send(response_json)
        await websocket.close()
    else:
        async for message in websocket:
            message_list = json.loads(message)
            logger.debug(f"Received message: {message_list}")
            len_message = len(message_list)
            logger.debug(f"Received message length: {len_message}")
            
            if message_list[0] == "EVENT":
                # Extract event information from message
                event_dict = message_list[1]
                await handle_new_event(event_dict, websocket)
            elif message_list[0] == "REQ":
                subscription_id = message_list[1]
                # Extract subscription information from message
                event_dict = {index: message_list[index] for index in range(len(message_list))}
                await handle_subscription_request(event_dict, websocket, subscription_id, origin)
            elif message_list[0] == "CLOSE":
                subscription_id = message_list[1]
                response = "NOTICE", f"closing {subscription_id}"
                if origin == "https://iris.to":
                    logger.debug(f"Sending CLOSE Response: {json.dumps(response)}")
                    await websocket.send(json.dumps(response))
                else:
                    logger.debug(f"Sending CLOSE Response: {json.dumps(response)} and closing websocket")
                    await websocket.send(json.dumps(response))
                    await websocket.close()
            else:
                logger.warning(f"Unsupported message format: {message_list}")


async def serialize(model):
    #Helper function to convert an SQLAlchemy model instance to a dictionary
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in columns)

async def handle_subscription_request(subscription_dict, websocket, subscription_id, origin):
    filters = subscription_dict

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
        if filters.get("#e"):
            query = query.filter(Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in filters.get("#p")))
        if filters.get("#e"):
            query = query.filter(Event.tags.any(lambda tag: tag[0] == 'd' and tag[1] in filters.get("#d")))   
        if filters.get("since"):
            query = query.filter(Event.created_at > filters.get("since"))
        if filters.get("until"):
            query = query.filter(Event.created_at < filters.get("until"))
        query_result = query.limit(filters.get("limit", 100)).all()

        for event in query_result:
            json_query_result = await serialize(event)
            response = "EVENT", subscription_id, json_query_result
            logger.debug(f"Response JSON = {json.dumps(response)}")
            await websocket.send(json.dumps(response))
        
        EOSE = "EOSE", subscription_id
        logger.debug(f"EOSE Resonse = {json.dumps(EOSE)}")
        await websocket.send(json.dumps(EOSE))
        if origin != "https://iris.to":
            logger.debug("Closing non Iris websocket")
            await websocket.close()


if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()