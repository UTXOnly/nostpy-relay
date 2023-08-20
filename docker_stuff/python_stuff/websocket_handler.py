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
client_ips = []

async def handle_websocket_connection(websocket: websockets.WebSocketServerProtocol, path: str) -> None:
    global unique_sessions, client_ips
    headers: websockets.Headers = websocket.request_headers
    referer: str = headers.get("referer", "")
    origin: str = headers.get("origin", "")
    real_ip = headers.get("X-Real-IP") or headers.get("X-Forwarded-For")
    
    if real_ip:
        logger.debug(f"Real!!! Client IP: {real_ip}")
        client_ips.append(real_ip)
    else:
        logger.warning("Unable to determine client IP.")
    logger.debug(f"New WebSocket connection established from URL: {referer or origin}")

    #if not rate_limiter.check_request(real_ip):
    #    logger.warning(f"Rate limit exceeded for client: {real_ip}")
    #    statsd.increment('nostr.client.rate_limited.count', tags=[f"client:{real_ip}"])
    #    return

    async with aiohttp.ClientSession() as session:
        uuid = websocket.id
        unique_sessions.append(uuid)
        logger.debug(f"UUID = {uuid}")
        try:
            async for message in websocket:
                if not rate_limiter.check_request(real_ip):
                    logger.warning(f"Rate limit exceeded for client: {real_ip}")
                    #["OK", "b1a649ebe8...", false, "rate-limited: slow down there chief"]
                    await websocket.close()
                    unique_sessions.remove(uuid)
                    client_ips.remove(real_ip)
                    statsd.increment('nostr.client.rate_limited.count', tags=[f"client:{real_ip}"])
                    return
                message_list: List[Union[str, Dict[str, Any]]] = json.loads(message)
                logger.debug(f"Received message: {message_list}")
                len_message: int = len(message_list)
                logger.debug(f"Received message length: {len_message}")

                if message_list[0] == "EVENT":
                    event_dict: Dict[str, Any] = message_list[1]
                    await send_event_to_handler(session=session, event_dict=event_dict, websocket=websocket)
                elif message_list[0] == "REQ":
                    subscription_id: str = message_list[1]
                    event_dict: List[Dict[str, Any]] = [{index: message_list[index]} for index in range(2, len(message_list))]
                    await send_subscription_to_handler(session=session, event_dict=event_dict, subscription_id=subscription_id, origin=origin, websocket=websocket)
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
        client_ips.remove(real_ip)

class ExtractedResponse:
    def __init__(self):
        self.event_type = None
        self.subscription_id = None
        self.results = None
    #def __init__(self, event_type: Optional[str], subscription_id: Optional[str], results: Optional[Union[str, Dict[str, Any]]]):
    #    self.event_type = event_type
    #    self.subscription_id = subscription_id
    #    self.results = results

    async def extract_response(self, response_data: Dict[str, Any]):
        self.event_type = response_data.get("event")
        self.subscription_id = response_data.get("subscription_id")
        self.results = response_data.get("results_json")
        comment = ""
        return self.event_type, self.subscription_id, self.results

    async def format_response(self, event_type, subscription_id, results, comment):
    
        if event_type == "OK":
            client_response: Tuple[str, Optional[str], str, Optional[str]] = event_type, subscription_id, results, comment
        elif event_type == "EVENT":
            events_to_send = []
            for event_result in results:
                client_response: Tuple[str, Optional[str], Dict[str, Any]] = event_type, subscription_id, event_result
                events_to_send.append(client_response)
            return events_to_send
        else:
            client_response: Tuple[str, Optional[str]] = event_type, subscription_id
    
        return client_response




async def send_event_to_handler(session: aiohttp.ClientSession, event_dict: Dict[str, Any], websocket: websockets.WebSocketServerProtocol) -> None:
    url: str = 'http://event_handler/new_event'
    async with session.post(url, data=json.dumps(event_dict)) as response:
        response_data: Dict[str, Any] = await response.json()
        response_object = ExtractedResponse()
        if response.status == 200:
            logger.debug(f"Sending response data: {response_data}")
            client_response = await response_object.extract_response(response_data)
            client_response = await response_object.format_response(event_type=response_object.event_type, subscription_id=response_object.subscription_id, results=response_object.results)
            await websocket.send(json.dumps(client_response))
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
    response_object = ExtractedResponse
    async with session.post(url, data=json.dumps(payload)) as response:
        response_data: Dict[str, Any] = await response.json()
        client_response = response_object.extract_response(response_data)
        logger.debug(f"Data type of response_data: {type(response_data)}, Response Data: {response_data}")
        
        logger.debug(f"Response received as: {response_data}")
        EOSE: Tuple[str, Optional[str]] = "EOSE", subscription_id

        if response.status == 200:
            logger.debug(f"Sending response data: {response_data}")
            response_list = await response_object.format_response(event_type=response_object.event_type, subscription_id=response_object.subscription_id, results=response_object.results)

            if response_object.event_type == "EOSE":
                
                await websocket.send(json.dumps(client_response))
            else:
                for event_item in response_list:
                    #client_response: Tuple[str, Optional[str], Dict[str, Any]] = event_type, subscription_id, event_item
                    #client_response = await extract_response(response_data)
                    await websocket.send(json.dumps(event_item))

            await websocket.send(json.dumps(EOSE))
        else:
            logger.debug(f"Response data is {response_data} but it failed")



if __name__ == "__main__":
    rate_limiter = TokenBucketRateLimiter(tokens_per_second=1, max_tokens=500)

    try:
        start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
        async def send_active_connections_metric():
            global unique_sessions, client_ips
            while True:
                await asyncio.sleep(5)
                try:
                    num_of_connections = len(unique_sessions)  # Get the number of connections
                    num_clients = len(client_ips)
                    statsd.gauge('nostr.websocket.active_connections', num_of_connections)
                    statsd.gauge('nostr.clients.connected', num_clients)
                    logger.debug(f"Active connections: {num_of_connections}")
                    logger.debug(f"Clients connected are: {client_ips}")

                except Exception as e:
                    logger.error(f"Error occurred while sending active connections metric: {e}")
        
        asyncio.get_event_loop().create_task(send_active_connections_metric())
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
    except Exception as e:
        logger.error(f"Error occurred while starting the server: {e}")
