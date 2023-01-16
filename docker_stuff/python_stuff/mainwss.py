import os
import json
import websockets
import asyncio
import psycopg2
from time import time
from threading import Thread
from typing import Callable
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, String, Integer, JSON, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.middleware.proxy_fix import ProxyFix

# App setup
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Event(Base):
    __tablename__ = 'event'

    id = Column(Integer, primary_key=True, index=True)
    pubkey = Column(String, index=True)
    kind = Column(String, index=True)
    payload = Column(JSON)
    created_at = Column(Integer, index=True)

    def __init__(self, pubkey: str, kind: str, payload: dict):
        self.pubkey = pubkey
        self.kind = kind
        self.payload = payload
        self.created_at = int(time.time())

Base.metadata.create_all(bind=engine)

# Routes
@app.route('/', methods=["GET"])
def index():
    return jsonify({"message": "Welcome to the Nostr Relay"})

connected_websockets = set()

@app.route('/event', methods=["POST"])
async def receive_event():
    event = request.get_json()
    if event is None:  # check if request.get_json() returned None
        return jsonify({"error": "Invalid JSON"}), 400
    pubkey = event.get("pubkey")
    kind = event.get("kind")
    payload = event.get("payload")

    # Save event to database
    try:
        with SessionLocal() as db:
            new_event = Event(pubkey, kind, event)
            db.add(new_event)
            db.commit()
    except Exception as e:
        return jsonify({"error": f"Failed to save event: {e}"}), 500

    # Send event to all connected websockets
    async def send_to_websockets(event):
        data = json.dumps(event)
        await asyncio.wait([ws.send(data) for ws in connected_websockets])

    # Check if request came from websocket or http
    if request.environ.get('wsgi.websocket'):
        websocket = request.environ['wsgi.websocket']
        connected_websockets.add(websocket)
        try:
            while True:
                event = json.loads(await websocket.recv())
                await send_to_websockets(event)
        finally:
            connected_websockets.remove(websocket)
    else:
        return jsonify({"message": "Event received and processed"})

@app.route('/events', methods=["GET"])
async def return_events(websocket: websockets.WebSocketServerProtocol):
    while True:
        message = await websocket.recv()
        message = json.loads(message)
        
        # Extract pubkey, kind and payload from message
        pubkey = message.get("pubkey")
        kind = message.get("kind")
        payload = message.get("payload")

        # Query the database
        with SessionLocal() as db:
            query = db.query(Event)
            if pubkey:
                query = query.filter(Event.pubkey == pubkey)
            if kind:
                query = query.filter(Event.kind == kind)
            if payload:
                for key, value in payload.items():
                    query = query.filter(and_(Event.payload.contains(key), Event.payload[key] == value))
            events = query.all()
            
            # Prepare the response
            results = [{'id': event.id, 'pubkey': event.pubkey, 'kind': event.kind, 'payload': event.payload, 'created_at': event.created_at} for event in events]
            await websocket.send(json.dumps(results))


if __name__ == '__main__':
    start_server = websockets.serve(return_events, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
