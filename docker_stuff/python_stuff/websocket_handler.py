import websockets
import logging
import json
import asyncio
import aiohttp
from ddtrace import tracer

tracer.configure(hostname='172.28.0.5', port=8126)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

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
                # Extract event information from message
                event_dict = message_list[1]
                await send_event_to_handler(session, event_dict)
            elif message_list[0] == "REQ":
                subscription_id = message_list[1]
                # Extract subscription information from message
                event_dict = {index: message_list[index] for index in range(len(message_list))}
                await send_subscription_to_handler(session, event_dict, subscription_id, origin, websocket)
            elif message_list[0] == "CLOSE":
                subscription_id = message_list[1]
                response = "NOTICE", f"closing {subscription_id}"
                logger.debug(f"Sending CLOSE Response: {json.dumps(response)} and closing websocket")
                await websocket.send(json.dumps(response))
                await websocket.close()
            else:
                logger.warning(f"Unsupported message format: {message_list}")

async def send_event_to_handler(session, event_dict):
    event_dict['session'] = session
    # Make a POST request to the event_handler container
    url = 'http://172.28.0.3/api/events'
    async with session.post(url, json=event_dict) as response:
        response_data = response.json()
        # Handle the response as needed
        pass

async def send_subscription_to_handler(session, event_dict, subscription_id, origin, websocket):
    # Make a POST request to the event_handler container with subscription data
    url = 'http://172.28.0.3/api/subscriptions'
    payload = {
        'event_dict': event_dict,
        'subscription_id': subscription_id,
        'origin': origin
    }
    async with session.post(url, json=payload) as response:
        # Wait for the response from the event_handler container
        response_data = response.json()

        # Handle the response as needed
        if response.status == 200:
            await websocket.send(json.dumps(response_data))

        else:
            await websocket.send(json.dumps(response_data))
            # Handle the error or send it back to the client


if __name__ == "__main__":
    start_server = websockets.serve(handle_websocket_connection, '0.0.0.0', 8008)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
