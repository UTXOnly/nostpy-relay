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

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")
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


Base.metadata.create_all(bind=engine)


connected_websockets = set()

async def event_handler(websocket, path):
    connected_websockets.add(websocket)
    subscriptions = []
    try:
        while True:
            if not websocket.open:  # check if connection is closed
                break
            message = await websocket.recv()
            message = json.loads(message)
            event = message.get("EVENT")
            print(event)

            # rest of the code


            if event:
                pubkey = event.get("pubkey")
                kind = event.get("kind")
                created_at = event.get("created_at")
                tags = event.get("tags")
                content = event.get("content")
                id = event.get("id")
                sig = event.get("sig")

                event_data = json.dumps([0, pubkey, created_at, kind, tags, content], sort_keys=True)
                computed_id = hashlib.sha256(event_data.encode()).hexdigest()

                #if id != computed_id:
                #    print("Event ID does not match computed event data. id: ", id, " computed_id: ", computed_id)
                #    await websocket.send(json.dumps({"error": "Event ID does not match computed event data"}))
                #    continue
                ## Verify signature
                #if not hmac.compare_digest(sig, hmac.new(bytes.fromhex(pubkey), event_data.encode(), hashlib.sha256).hexdigest()):
                #    print("Invalid signature. sig: ", sig, " calculated_sig: ", hmac.new(bytes.fromhex(pubkey), event_data.encode(), hashlib.sha256).hexdigest())
                #    await websocket.send(json.dumps({"error": "Invalid signature"}))
                #    continue
#
                with SessionLocal() as db:
                    new_event = Event(id=id, pubkey=pubkey, kind=kind, created_at=created_at, tags=tags, content=content, sig=sig)
                    db.add(new_event)
                    db.commit()
                await websocket.send(json.dumps({"message": "Event received and processed"}))

            elif message.get("REQ"):
                subscription_id = message.get("subscription_id")
                filters = message.get("filters")
                with SessionLocal() as db:
                    query = db.query(Event)
                    if filters.get("ids"):
                        query = query.filter(Event.id.in_(filters.get("ids")))
                    if filters.get("authors"):
                        query = query.filter(Event.pubkey.in_(filters.get("authors")))
                    if filters.get("kinds"):
                        query = query.filter(Event.kind.in_([filters.get("kinds")]))
                    if filters.get("#e"):
                        query = query.filter(Event.tags.any(lambda tag: tag[0] == 'e' and tag[1] in filters.get("#e")))
                    if filters.get("#p"):
                        query = query.filter(Event.tags.any(lambda tag: tag[0] == 'p' and tag[1] in filters.get("#p")))
                    if filters.get("since"):
                        query = query.filter(Event.created_at > filters.get("since"))
                    if filters.get("until"):
                        query = query.filter(Event.created_at < filters.get("until"))
                    query_result = query.limit(filters.get("limit")).all()
                    subscription_data = {"subscription_id": subscription_id, "filters": filters, "query_result": query_result}
                    subscriptions.append(subscription_data)
                    print(subscription_data)
                    await websocket.send(json.dumps({"subscription_id": subscription_id, "query_result": query_result}))
    finally:
        connected_websockets.remove(websocket)

start_server = websockets.serve(event_handler, '0.0.0.0', 8008)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()


