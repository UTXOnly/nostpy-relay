import asyncio
import json
import websockets
import random
import string
import hmac
import hashlib
from time import time

base_url = 'ws://localhost:8008'

def create_random_event():
    # Generate random pubkey, kind, and payload values
    pubkey = "npub1g5pm4gf8hh7skp2rsnw9h2pvkr32sdnuhkcx9yte7qxmrg6v4txqqudjqv"
    kind = 1 #random.randint(0, 10)
    created_at = int(time())
    tags = []
    content = "This is a test from nost-py, a relay written in Python. If you are seeing this, I am sucessuflly storing events and serving client quieries"

    event = {
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": tags,
        "content": content
    }
    event_data = json.dumps([0, pubkey, created_at, kind, tags, content], sort_keys=True)
    print(event_data)

    event_id = hashlib.sha256(event_data.encode()).hexdigest()
    print(event_id)
    
    # decode the pubkey string before using it in the hmac
    
    sig = hmac.new(pubkey.encode(), event_data.encode(), hashlib.sha256).hexdigest()
    print(sig)

    event["id"] = event_id
    event["sig"] = sig
    return event

async def post_event(note: dict):
    """
    Sends a message to the websocket server with the provided nostr note
    """
    while True:
        try:
            async with websockets.connect(base_url) as websocket:
                async def ping():
                    while True:
                        await asyncio.sleep(30)
                        await websocket.ping()
                pinger = asyncio.create_task(ping())
                try:
                    event_data = json.dumps({"EVENT": note})
                    await websocket.send(event_data)
                    response = await websocket.recv()
                    return json.loads(response)
                finally:
                    pinger.cancel()
                    await websocket.close()
        except websockets.exceptions.ConnectionClosedError:
            print("Error: received 1011 (unexpected error); then sent 1011 (unexpected error). Retrying...")
            await asyncio.sleep(1)


async def test_query():
    for i in range(3):
        try:
            async with websockets.connect(base_url) as websocket:
                filters = {
                    "authors": ["npub1g5pm4gf8hh7skp2rsnw9h2pvkr32sdnuhkcx9yte7qxmrg6v4txqqudjqv"],
                    "kind": [1,2],
                    "since": 1600000000,
                    "until": 1600001000,
                    "limit": 10
                }
                query_message = json.dumps({"REQ": "query", "subscription_id": "randomstring", "filters": filters})
                await websocket.send(query_message)
                response = await websocket.recv()
                print(response)
                return response
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Error: {e}. Retrying...")
            await asyncio.sleep(1)
    print("Error: Could not connect to websocket. Giving up.")



async def main():
    event = create_random_event()
    post_response = await post_event(event)
    print(post_response)
    query_response = await test_query()
    print(query_response)
if __name__ == "__main__":
    asyncio.run(main())




