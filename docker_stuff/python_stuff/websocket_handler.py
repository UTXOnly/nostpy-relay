import asyncio
import json
import logging
import aiohttp
import websockets
from websockets.server import WebSocketServer
from collections import defaultdict
import time
from logging.handlers import RotatingFileHandler
from ddtrace import tracer
from datadog import initialize, statsd
from aiohttp.client import ClientResponse
from typing import Dict, Any, List, Tuple, Union, Optional

options: Dict[str, Any] = {
    'statsd_host': '172.28.0.5',
    'statsd_port': 8125
}

initialize(**options)

tracer.configure(hostname='172.28.0.5', port=8126)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file: str = './logs/websocket_handler.log'
handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class TokenBucketRateLimiter:
    def __init__(self, tokens_per_second: int, max_tokens: int):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = defaultdict(lambda: self.max_tokens)
        self.last_request_time = defaultdict(lambda: 0)

    def _get_tokens(self, client_id: str) -> None:
        current_time = time.time()
        time_passed = current_time - self.last_request_time[client_id]
        new_tokens = int(time_passed * self.tokens_per_second)
        self.tokens[client_id] = min(self.tokens[client_id] + new_tokens, self.max_tokens)
        self.last_request_time[client_id] = current_time

    def check_request(self, client_id: str) -> bool:
        self._get_tokens(client_id)
        if self.tokens[client_id] >= 1:
            self.tokens[client_id] -= 1
            return True
        return False

unique_sessions = []

async def handle_websocket_connection(websocket: websockets.WebSocketServerProtocol, path: str) -> None:
    global unique_sessions
    headers: websockets.Headers = websocket.request_headers
    referer: str = headers.get("referer", "")
    origin: str = headers.get("origin", "")
    logger.debug(f"New WebSocket connection established from URL: {referer or origin}")

    client_ip = websocket.remote_address[0]
    logger.debug(f"Client IP is {client_ip}")
    if not rate_limiter.check_request(client_ip):
        logger.warning(f"Rate limit exceeded for client: {client_ip}")
        return

    async with aiohttp.ClientSession() as session:
        uuid = websocket.id
        unique_sessions.append(uuid)
        logger.debug(f"UUID = {uuid}")
        try:
            async for message in websocket:
                message_list: List[Union[str, Dict[str, Any]]] = json.loads(message)
                logger.debug(f"Received message: {message_list}")
                len_message: int = len(message_list)
                logger.debug(f"Received message length: {len_message}")

                if message_list[0] == "EVENT":
                    event_dict: Dict[str, Any] = message_list[1]
                    await send_event_to_handler(session, event_dict)
                elif message_list[0] == "REQ":
                    subscription_id: str = message_list[1]
                    event_dict: List[Dict[str, Any]] = [{index: message_list[index]} for index in range(2, len(message_list))]
                    await send_subscription_to_handler(session, event_dict, subscription_id, origin, websocket)
                elif message_list[0] == "CLOSE":
                    subscription_id: str = message_list[1]
                    response: Tuple[str, str] = "NOTICE", f"closing {subscription_id}"
                    break  # Exit the loop when CLOSE message is received
                else:
                    logger.warning(f"Unsupported message format: {message_list}")
        except Exception as e:
            logger.error(f"Error occurred while starting the server: {e}")
            raise

        unique_sessions.remove(uuid)


async def send_event_to_handler(session: aiohttp.ClientSession, event_dict: Dict[str, Any]) -> None:
    url: str = 'http://event_handler/new_event'
    async with session.post(url, data=json.dumps(event_dict)) as response:
        response_data: Dict[str, Any] = await response.json()
        logger.debug(f"Received response from Event Handler {response_data}")

async def send_subscription_to_handler(
    session: aiohttp.ClientSession,
    event_dict: List[Dict[str, Any]],
    subscription_id: str,
    origin: str,
    websocket: websockets.WebSocketServerProtocol
) -> None:
    url: str = 'http://event_handler/subscription'
    payload: Dict[str, Any] = {
        'event_dict': event_dict,
        'subscription_id': subscription_id,
        'origin': origin
    }
    async with session.post(url, data=json.dumps(payload)) as response:
        response_data: Dict[str, Any] = await response.json()
        logger.debug(f"Data type of response_data: {type(response_data)}, Response Data: {response_data}")
        event_type: Optional[str] = response_data.get("event")
        subscription_id: Optional[str] = response_data.get("subscription_id")
        results: Optional[List[Dict[str, Any]]] = response_data.get("results_json")
        logger.debug(f"Response received as: {response_data}")
        EOSE: Tuple[str, Optional[str]] = "EOSE", subscription_id

        if response.status == 200:
            logger.debug(f"Sending response data: {response_data}")

            if event_type == "EOSE":
                client_response: Tuple[str, Optional[str]] = event_type, subscription_id
                await websocket.send(json.dumps(client_response))
            else:
                if results:
                    for event_item in results:
                        client_response: Tuple[str, Optional[str], Dict[str, Any]] = event_type, subscription_id, event_item
                        await websocket.send(json.dumps(client_response))

            await websocket.send(json.dumps(EOSE))
        else:
            logger.debug(f"Response data is {response_data} but it failed")

async def count_active_connections(websockets_server: WebSocketServer) -> int:

    open_sockets = str(WebSocketServer.sockets)
    logger.debug(f"Open sockets are: {open_sockets}")
    logger.debug(f"open sockert type is {type(open_sockets)}")
    #active_connections = len(websockets_server.)
    #logger.debug(f"Number of active connections: {active_connections}")
    #return active_connections


if __name__ == "__main__":
    rate_limiter = TokenBucketRateLimiter(tokens_per_second=1, max_tokens=100)

    try:
        start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
        
        
        async def send_active_connections_metric():
            global unique_sessions
            while True:
                await asyncio.sleep(1)
                try:
                    #active_connections = await count_active_connections(start_server.ws_server)
                    #sockets = start_server.ws_server.sockets
                    #sockets = 
                    num_of_connections = len(unique_sessions)  # Get the number of connections
                    statsd.gauge('nostr.websocket.active_connections', num_of_connections)
                    logger.debug(f"Active connections: {num_of_connections}")
                    logger.debug(f"Number of connections: {num_of_connections}")  # Print the number of connections
                    #logger.debug(f"Open sockets are: {sockets}")
                except Exception as e:
                    logger.error(f"Error occurred while sending active connections metric: {e}")
        
        asyncio.get_event_loop().create_task(send_active_connections_metric())
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
    except Exception as e:
        logger.error(f"Error occurred while starting the server: {e}")
