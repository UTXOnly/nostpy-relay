import asyncio
import json
import logging
import aiohttp
import websockets
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

active_connections = 0

async def handle_websocket_connection(websocket: websockets.WebSocketServerProtocol, path: str) -> None:
    global active_connections
    active_connections += 1
    headers: websockets.Headers = websocket.request_headers
    referer: str = headers.get("referer", "")  # Snort
    origin: str = headers.get("origin", "")
    logger.debug(f"New websocket connection established from URL: {referer or origin}")

    async with aiohttp.ClientSession() as session:
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
            else:
                logger.warning(f"Unsupported message format: {message_list}")
            active_connections -= 1

async def send_event_to_handler(session: aiohttp.ClientSession, event_dict: Dict[str, Any]) -> None:
    url: str = 'http://event_handler/new_event'
    async with session.post(url, data=json.dumps(event_dict)) as response:
        response_data: Dict[str, Any] = await response.json()
        logger.debug(f"Recieved response from Event Handler {response_data}")

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
    async with aiohttp.ClientSession() as session:
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

if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    async def send_active_connections_metric():
        while True:
            await asyncio.sleep(30)
            statsd.gauge('nostr.websocket.active_connections', active_connections)
    asyncio.get_event_loop().create_task(send_active_connections_metric())
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
