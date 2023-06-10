import asyncio
import json
import logging
import aiohttp
import asyncpg
import uvloop
import uvicorn
import fastapi

from ddtrace import tracer
from fastapi import FastAPI, WebSocket, Request

tracer.configure(hostname='172.28.0.5', port=8126)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.websocket("/")
async def handle_websocket_connection(websocket: WebSocket):
    headers = websocket.headers
    referer = headers.get("referer")  # Snort
    origin = headers.get("origin")
    logger.info(f"New websocket connection established from URL: {referer or origin}")
    await websocket.accept()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                message = await websocket.receive_json()
                logger.info(f"Received message: {message}")
                len_message = len(message)
                logger.info(f"Received message length: {len_message}")

                actions = {
                    "EVENT": send_event_to_handler,
                    "REQ": send_subscription_to_handler,
                    "CLOSE": close_connection
                }
                
                action = actions.get(message[0])
                if action:
                    if message[0] == "REQ":
                        subscription_id = message[1]
                        response = await action(session, message, subscription_id, origin, websocket )
                    else:
                        message = message[1]
                        response = await action(session, message, origin)
                else:
                    logger.warning(f"Unsupported message format: {message}")


            except RuntimeError as e:
                logger.error(f"WebSocket connection error: {str(e)}")
                # Close the connection or handle the error as needed
                await websocket.close()
                break


async def send_event_to_handler(session: aiohttp.ClientSession, event_dict, origin: str):
    url = 'http://event_handler/new_event'
    async with session.post(url, data=json.dumps(event_dict)) as response:
        response_data = await response.json()
        logger.info(f"Received response from Event Handler {response_data}")


async def send_subscription_to_handler(session: aiohttp.ClientSession, event_dict: dict, subscription_id: str, origin: str, websocket):
    payload = {
            'event_dict': event_dict,
            'subscription_id': subscription_id,
            'origin': origin}
    try:
        async with session.post('http://query_service/subscription', data=json.dumps(payload)) as response:
            if response.status != 200:
                logger.info(f"Response data is {response} but it failed")
                # Handle the error or send it back to the client
                return

            response_data = await response.json()
            logger.info(f"Data type of response_data: {type(response_data)}, Response Data: {response_data}")

            response_data = await response.json()
            logger.debug(f"response_data: {response_data}")
            
            event_type = response_data.get("event")
            logger.debug(f"event_type: {event_type}")
            
            subscription_id = response_data.get("subscription_id")
            logger.debug(f"subscription_id: {subscription_id}")
            
            results = response_data.get("results_json")
            logger.debug(f"results: {results}")
            
            logger.info(f"Response received as: {response_data}")

            EOSE = "EOSE", subscription_id

            if event_type == "EOSE":
                client_response = event_type, subscription_id
                await websocket.send(json.dumps(client_response))
            else:
                for event_item in results:
                    client_response = event_type, subscription_id, event_item
                    await websocket.send(json.dumps(client_response))

                await websocket.send(json.dumps(EOSE))

            logger.info(f"Sending response data: {response_data}")

    except Exception as e:
        logger.error(f"Error occurred while processing the subscription - {str(e)}")
        # Handle the error or send it back to the client
        pass


async def close_connection():
    print("NOTICE", f"closing connection")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8008)
