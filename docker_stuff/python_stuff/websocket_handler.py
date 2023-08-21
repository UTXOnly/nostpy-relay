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
    
class ExtractedResponse:
    def __init__(self, response_data):
        self.event_type = response_data.get("event")
        self.subscription_id = response_data.get("subscription_id")
        self.results = response_data.get("results_json")
        self.comment = ""

    async def format_response(self):
    
        if self.event_type == "OK":
            client_response: Tuple[str, Optional[str], str, Optional[str]] = self.event_type, self.subscription_id, self.results, self.comment
        elif self.event_type == "EVENT":
            events_to_send = []
            for event_result in self.results:
                client_response: Tuple[str, Optional[str], Dict[str, Any]] = self.event_type, self.subscription_id, event_result
                events_to_send.append(client_response)
            return events_to_send
        else:
            #Return EOSE
            client_response: Tuple[str, Optional[str]] = self.event_type, self.subscription_id
    
        return client_response


class WebsocketMessages:
    def __init__(self, message: List[Union[str, Dict[str, Any]]], websocket):
        self.event_type = message[0]
        if self.event_type == "REQ" or self.event_type == "CLOSE":
            self.subscription_id: str = message[1]
            self.event_payload: List[Dict[str, Any]] = [{index: message[index]} for index in range(2, len(message))]
        else:
            self.event_payload: Dict[str, Any] = message[1]
        headers: websockets.Headers = websocket.request_headers
        #self.referer: str = headers.get("referer", "")
        #self.origin: str = headers.get("origin", "")
        self.client_ip: str = headers.get("X-Real-IP") or headers.get("X-Forwarded-For")
        logger.debug(f"Client IP is {self.client_ip}")
        self.uuid: str = websocket.id

unique_sessions = []
client_ips = []

async def handle_websocket_connection(websocket: websockets.WebSocketServerProtocol, path: str) -> None:
    global unique_sessions, client_ips

    async with aiohttp.ClientSession() as session:
        place_holder = 0
                
        try:
            async for message in websocket:
                message_list: List[Union[str, Dict[str, Any]]] = json.loads(message)
                ws_message = WebsocketMessages(message=message_list, websocket=websocket)
                unique_sessions.append(ws_message.uuid)
                logger.debug(f"UUID = {ws_message.uuid}")
                
                if not rate_limiter.check_request(ws_message.client_ip):
                    logger.warning(f"Rate limit exceeded for client: {ws_message.client_ip}")
                    if ws_message.event_type == "REQ":
                        rate_limit_response: Tuple[str, Optional[str], str, Optional[str]] = "OK", ws_message.subscription_id, "false", "rate-limited: slow down there chief"
                        #unique_sessions.remove(ws_message.uuid)
                        #client_ips.remove(ws_message.client_ip)
                        statsd.increment('nostr.client.rate_limited.count', tags=[f"client:{ws_message.client_ip}"])
                        await websocket.send(json.dumps(rate_limit_response))
                        await websocket.close()
                        return

                if ws_message.event_type == "EVENT":
                    logger.debug(f"Event to be sent payload is: {ws_message.event_payload} of type {type(ws_message.event_payload)}")
                    await send_event_to_handler(session=session, event_dict=dict(ws_message.event_payload), websocket=websocket)
                elif ws_message.event_type == "REQ":
                    await send_subscription_to_handler(session=session, event_dict=ws_message.event_payload, subscription_id=ws_message.subscription_id, websocket=websocket)
                elif ws_message.event_type == "CLOSE":
                    response: Tuple[str, str] = "NOTICE", f"closing {ws_message.subscription_id}"
                    await websocket.send(json.dumps(response))
                    
                else:
                    logger.warning(f"Unsupported message format: {message_list}")
        except Exception as e:
            logger.error(f"Error occurred while starting the server: {e}")
            raise

        unique_sessions.remove(ws_message.uuid)
        client_ips.remove(ws_message.client_ip)

async def send_event_to_handler(session: aiohttp.ClientSession, event_dict: Dict[str, Any], websocket: websockets.WebSocketServerProtocol) -> None:
    url: str = 'http://event_handler/new_event'
    try:
        async with session.post(url, data=json.dumps(event_dict)) as response:
            logger.debug(f"Response event handler variable is {response}")
            response_data: Dict[str, Any] = await response.json()
            logger.debug(f"Received response from Event Handler {response_data}, data types is {type(response_data)}")
            response_object = ExtractedResponse(response_data)
            if response.status == 200:
                formatted_response = await response_object.format_response()
                logger.debug(f"Formatted response data from send_event_to_handler function: {formatted_response}")
                await websocket.send(json.dumps(formatted_response))
    except Exception as e:
        logger.error(f"An error occurred while sending the event to the handler: {e}")

        
async def send_subscription_to_handler(
    session: aiohttp.ClientSession,
    event_dict: List[Dict[str, Any]],
    subscription_id: str,
    websocket: websockets.WebSocketServerProtocol
) -> None:
    url: str = 'http://event_handler/subscription'
    payload: Dict[str, Any] = {
        'event_dict': event_dict,
        'subscription_id': subscription_id
    }
    
    async with session.post(url, data=json.dumps(payload)) as response:
        response_data: Dict[str, Any] = await response.json()
        response_object = ExtractedResponse(response_data=response_data)
        logger.debug(f"Data type of response_data: {type(response_data)}, Response Data: {response_data}")
        
        logger.debug(f"Response received as: {response_data}")
        EOSE: Tuple[str, Optional[str]] = "EOSE", response_object.subscription_id

        if response.status == 200 and response_object.event_type == "EVENT":
            response_list = await response_object.format_response()
            logger.debug(f"Response list is : {response_list}")
            for event_item in response_list:
                logger.debug(f"Final response from REQ to ws client: {event_item}")
                await websocket.send(json.dumps(event_item))

            await websocket.send(json.dumps(EOSE))
        else:
            await websocket.send(json.dumps(EOSE))
            logger.debug(f"Response data is {response_data} but it failed")


if __name__ == "__main__":
    rate_limiter = TokenBucketRateLimiter(tokens_per_second=1, max_tokens=2000)

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
