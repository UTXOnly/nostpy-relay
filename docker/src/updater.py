from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import requests
import uvloop
import websockets
import json
import hashlib
import logging
import bech32
import secp256k1


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/updater", response_class=StreamingResponse)
async def read_root():
    file_path = Path("static/index.html")
    return file_path.read_text()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class NoteUpdater:
    def __init__(self, pubkey_to_query) -> None:
        self.pubkey_to_query = pubkey_to_query

    def bech32_to_hex(self, npub):
        hrp, data = bech32.bech32_decode(npub)
        decoded_bytes = bech32.convertbits(data, 5, 8, False)
        return bytes(decoded_bytes).hex()

    def process_pubkey(self):
        if self.pubkey_to_query.startswith("npub"):
            hex_pubkey = self.bech32_to_hex(self.pubkey_to_query)
            self.pubkey_to_query = hex_pubkey
        else:
            logger.debug(f"Hex value provided: {self.pubkey_to_query}")

    async def query_relay(self, relay):
        """Query a relay and yield results."""
        try:
            async with websockets.connect(relay) as ws:
                query_dict = {
                    "kinds": [0],  # Example kinds, change as necessary
                    "limit": 300,
                    "authors": [self.pubkey_to_query]
                }

                query_ws = json.dumps(("REQ", "metadataupdater", query_dict))

                await ws.send(query_ws)
                logger.info(f"Query sent to relay {relay}: {query_ws}")

                async for message in ws:
                    response = json.loads(message)

                    if response[0] == "EVENT" and response[2]["kind"] == 0:
                        yield {
                            "relay": relay,
                            "event": response[2]
                        }
        except Exception as exc:
            logger.error(f"Error querying {relay}: {exc}")

    async def gather_queries(self):
        online_relays = await self._get_online_relays()
        tasks = [self.query_relay(relay) for relay in online_relays]
        return tasks  # Return the list of coroutine objects

    async def _get_online_relays(self):
        URL = "https://api.nostr.watch/v1/online"
        response = requests.get(URL, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Error: Unable to fetch data from API")
            return []

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

@app.post("/updater/scan")
async def handle_pubkey_scan(request: Request):
    """Handle scan requests and stream responses using a generator."""
    data = await request.json()
    pubkey = data.get("pubkey")

    if not pubkey:
        return JSONResponse(content={"error": "pubkey not provided"}, status_code=400)

    updater = NoteUpdater(pubkey)
    updater.process_pubkey()

    async def result_generator():
        """Generator to stream results back to the client."""
        tasks = await updater.gather_queries()
        for task in asyncio.as_completed(tasks):  # Now tasks are awaitable
            async for result in await task:
                yield json.dumps(result) + "\n"

    return StreamingResponse(result_generator(), media_type="application/json")

