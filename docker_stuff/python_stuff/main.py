import os
import json
import websockets
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

@app.route('/event', methods=["POST"])
def receive_event():
    event = request.get_json()
    pubkey = event.get("pubkey")
    kind = event.get("kind")
    # process event here
    try:
        # Save event to database
        with SessionLocal() as db:
            new_event = Event(pubkey, kind, event)
            db.add(new_event)
            db.commit()
    except Exception as e:
        # Handle error
        return jsonify({"error": f"Failed to save event: {e}"}), 500

    return jsonify({"message": "Event received and processed"})


@app.route('/events', methods=["GET"])
def return_events(pubkey: str = None, kind: str = None, payload: dict = None):
    with SessionLocal() as db:
        query = db.query(Event)
        if pubkey:
            query = query.filter(Event.pubkey == pubkey)
        if kind:
            query = query.filter(Event.kind == kind)
        if payload:
            if isinstance(payload, str):
                payload = json.loads(payload)
            for key, value in payload.items():
                query = query.filter(and_(Event.payload.contains(key), Event.payload[key] == value))
        events = query.all()
        results = [{'id': event.id, 'pubkey': event.pubkey, 'kind': event.kind, 'payload': event.payload, 'created_at': event.created_at} for event in events]
        return jsonify(results)




def events():
    async def handle_websocket(websocket, path):
        # Handle incoming messages from the websocket here
        pass

    return websockets.serve(handle_websocket, '/events')
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8008)
