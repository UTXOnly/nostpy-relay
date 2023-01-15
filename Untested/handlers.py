import asyncio
import json
from typing import List
import websockets

class WebSocket:
    def __init__(self, conn: websockets.WebSocketServerProtocol):
        self.conn = conn
        self.mutex = asyncio.Lock()

    async def write_json(self, any_obj: dict):
        async with self.mutex:
            await self.conn.send(json.dumps(any_obj))

    async def write_message(self, t: int, b: bytes):
        async with self.mutex:
            await self.conn.send(b)

class Server:
    def __init__(self, relay: dict, router: dict, clients: dict):
        self.relay = relay
        self.router = router
        self.clients = clients

    async def handle_websocket(self, w: dict, r: dict):
        store = self.relay["Storage"]()
        advanced_deleter, _ = store.get("AdvancedDeleter")
        advanced_querier, _ = store.get("AdvancedQuerier")

        conn = await websockets.upgrade(w, r)
        self.clients["clients_mu"].acquire()
        self.clients["clients"][conn] = {}
        self.clients["clients_mu"].release()
        ticker = asyncio.create_task(asyncio.sleep(self.clients["ping_period"]))

        ws = WebSocket(conn)

        # reader
# reader
    async def reader():
        nonlocal ticker
        try:
            while True:
                typ, message = await conn.recv()
                if typ == websockets.Message.ping:
                    await ws.write_message(websockets.Message.close, websockets.CloseMessage(websockets.CloseReason.normal, ""))
                ticker.cancel()
                ticker = asyncio.create_task(asyncio.sleep(self.clients["ping_period"]))
        except websockets.ConnectionClosed as e:
            pass
        finally:
            self.clients["clients_mu"].acquire()
            del self.clients["clients"][conn]
            self.clients["clients_mu"].release()
            await conn.close()
