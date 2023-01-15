import os
import json
import time
from threading import Thread
from typing import Callable
from flask import Flask, request
from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from storage import get_storage
from relayer import Server

backend = get_storage('postgresql', 'postgres://user:password@host:port/database')
server = Server(storage=backend)
server.start()


app = Flask(__name__)

class Relay:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def start(self, host: str='127.0.0.1', port: int=0):
        self.server = Thread(target=app.run, kwargs={'host': host, 'port': port})
        self.server.start()

    def stop(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()

    def name(self):
        return "BasicRelay"

    def init(self):
        pass

    def on_initialized(self):
        # every hour, delete all very old events
        def delete_old_events():
            while True:
                time.sleep(60 * 60)
                with self.SessionLocal() as db:
                    db.query(Event).filter(Event.created_at < time.time() - 60*60*24*90).delete() # 3 months
        t = Thread(target=delete_old_events)
        t.start()
    
    def accept_event(self, event: dict):
        # block events that are too large
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

    def __init__(self, pubkey)
