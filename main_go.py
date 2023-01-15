import os
import json
import time
from typing import Callable
from flask import Flask, request
from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

app = Flask(__name__)

class Relay:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def start(self, host: str='127.0.0.1', port: int=0):
        app.run(host=host, port=port)

    def accept_event(self, event: dict):
        json_b = json.dumps(event)
        if len(json_b) > 10000:
            return False
        return True

    def before_save(self, event: dict):
        pass

    def after_save(self, event: dict):
        with self.SessionLocal() as db:
            db.query(Event).filter(Event.pubkey == event['pubkey'], Event.kind == event['kind']).order_by(Event.created_at.desc()).offset(100).delete()

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

while True:
    time.sleep(1)
