import contextlib
from threading import Thread
from typing import Callable
from flask import Flask, request

app = Flask(__name__)

class TestRelay:
    def __init__(self, name: str, storage, on_initialized: Callable=None, on_shutdown: Callable=None, accept_event: Callable=None):
        self.name = name
        self.storage = storage
        self.on_initialized = on_initialized
        self.on_shutdown = on_shutdown
        self.accept_event = accept_event
        
    def init(self):
        pass
    
    def start(self, host: str='127.0.0.1', port: int=0):
        self.server = Thread(target=app.run, kwargs={'host': host, 'port': port})
        self.server.start()

    def stop(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()

class TestStorage:
    def __init__(self, init: Callable=None, query_events: Callable=None, delete_event: Callable=None, save_event: Callable=None):
        self.init = init
        self.query_events = query_events
        self.delete_event = delete_event
        self.save_event = save_event

def start_test_relay(host: str='127.0.0.1', port: int=0, tr: TestRelay):
    tr.start(host=host, port=port)
    tr.on_initialized()
    return tr

def stop_test_relay(tr: TestRelay):
    tr.stop()
    tr.on_shutdown()

