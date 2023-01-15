import threading

from websocket import WebSocket

class WebSocket:
    def __init__(self, conn: WebSocket):
        self.conn = conn
        self.mutex = threading.Lock()
    
    def write_json(self, data: dict):
        with self.mutex:
            return self.conn.send_json(data)
        
    def write_message(self, message_type: int, message: str):
        with self.mutex:
            return self.conn.send_message(message, message_type)
