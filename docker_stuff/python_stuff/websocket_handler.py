import asyncio
import json
import logging
import aiohttp
from ddtrace import tracer
import websockets
from logging.handlers import TimedRotatingFileHandler


tracer.configure(hostname='172.28.0.5', port=8126)

#logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)
#logging.basicConfig(filename='./logs/websocket_handler.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a timed rotating file handler
log_file = './logs/event_handler.log'
handler = TimedRotatingFileHandler(log_file, when='m', interval=1, backupCount=5)

# Set the log format
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

async def handle_websocket_connection(websocket, path):
    headers = websocket.request_headers
    referer = headers.get("referer")  # Snort
    origin = headers.get("origin")
    logger.debug(f"New websocket connection established from URL: {referer or origin}")

    async with aiohttp.ClientSession() as session:
        async for message in websocket:
            message_list = json.loads(message)
            logger.debug(f"Received message: {message_list}")
            len_message = len(message_list)
            logger.debug(f"Received message length: {len_message}")

            if message_list[0] == "EVENT":
                event_dict = message_list[1]
                await send_event_to_handler(session, event_dict)
            elif message_list[0] == "REQ":
                subscription_id = message_list[1]
                event_dict = [{index: message_list[index]} for index in range(2, len(message_list))]
                await send_subscription_to_handler(session, event_dict, subscription_id, origin, websocket)
            elif message_list[0] == "CLOSE":
                subscription_id = message_list[1]
                response = "NOTICE", f"closing {subscription_id}"
            else:
                logger.warning(f"Unsupported message format: {message_list}")

async def send_event_to_handler(session, event_dict):
    url = 'http://event_handler/new_event'
    async with session.post(url, data=json.dumps(event_dict)) as response:
        response_data = await response.json()
        logger.debug(f"Recieved response from Event Handler {response_data}")

async def send_subscription_to_handler(session, event_dict, subscription_id, origin, websocket):
    url = 'http://event_handler/subscription'
    payload = {
        'event_dict': event_dict,
        'subscription_id': subscription_id,
        'origin': origin
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=json.dumps(payload)) as response:
            response_data = await response.json()
            logger.debug(f"Data type of response_data: {type(response_data)}, Response Data: {response_data}")
            event_type = response_data.get("event")
            subscription_id = response_data.get("subscription_id")
            results = response_data.get("results_json")
            logger.debug(f"Response received as: {response_data}")
            EOSE = "EOSE", subscription_id

            if response.status == 200:
                logger.debug(f"Sending response data: {response_data}")

                if event_type == "EOSE":
                    client_response = event_type, subscription_id
                    await websocket.send(json.dumps(client_response))
                else:
                    for event_item in results:
                        client_response = event_type , subscription_id, event_item
                        await websocket.send(json.dumps(client_response))
              
                await websocket.send(json.dumps(EOSE))
            else:
                logger.debug(f"Response data is {response_data} but it failed")
if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()