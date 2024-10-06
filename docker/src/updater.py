from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
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
import gc

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/updater", response_class=HTMLResponse)
async def read_root():
    gc.collect()
    file_path = Path("static/index.html")
    return file_path.read_text()


logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class NoteUpdater:
    def __init__(self, pubkey_to_query) -> None:
        self.events_found = []
        self.good_relays = []
        self.bad_relays = []
        self.updated_relays = []
        self.unreachable_relays = []
        self.pubkey_to_query = pubkey_to_query
        self.timestamp_set = set()
        self.high_time = 1
        self.all_good_relays = {}
        self.relay_event_pair = {}
        self.old_relays = []
        self.latest_note = ""

    def bech32_to_hex(self, npub):
        hrp, data = bech32.bech32_decode(npub)
        decoded_bytes = bech32.convertbits(data, 5, 8, False)
        return bytes(decoded_bytes).hex()

    def process_pubkey(self):
        if self.pubkey_to_query.startswith("npub"):
            hex_pubkey = self.bech32_to_hex(self.pubkey_to_query)
            logger.info(f"Converted npub to hex: {hex_pubkey}")
            self.pubkey_to_query = hex_pubkey
        else:
            logger.debug(f"Hex value provided: {self.pubkey_to_query}")

    def cleanup_memory(self):
        """Function to explicitly clean up large attributes."""
        self.events_found.clear()
        self.good_relays.clear()
        self.bad_relays.clear()
        self.updated_relays.clear()
        self.unreachable_relays.clear()
        self.relay_event_pair.clear()
        self.old_relays.clear()
        self.all_good_relays.clear()
        gc.collect()

    def _get_online_relays(self):
        URL = "https://api.nostr.watch/v1/online"
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                yield item  # Yield each relay one by one
            logger.info(f"{len(data)} online relays discovered")
        else:
            logger.error("Error: Unable to fetch data from API")

    def calc_event_id(self, public_key: str, created_at: int, kind_number: int, tags: list, content: str) -> str:
        data = [0, public_key, created_at, kind_number, tags, content]
        data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(data_str.encode("UTF-8")).hexdigest()

    def verify_signature(self, event_id: str, pubkey: str, sig: str) -> bool:
        try:
            pub_key = secp256k1.PublicKey(bytes.fromhex("02" + pubkey), True)
            result = pub_key.schnorr_verify(
                bytes.fromhex(event_id), bytes.fromhex(sig), None, raw=True
            )
            if result:
                logger.debug(f"Verification successful for event: {event_id}")
                return True
            else:
                logger.error(f"Verification failed for event: {event_id}")
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"Error verifying signature for event {event_id}: {e}")
            return False

    async def query_relay(self, relay, kinds=None):
        try:
            async with websockets.connect(relay) as ws:
                query_dict = {
                    "kinds": kinds or [0],
                    "limit": 3,
                    "since": 179340343,
                    "authors": [self.pubkey_to_query],
                }
                query_ws = json.dumps(("REQ", "metadataupdater", query_dict))
                await ws.send(query_ws)
                logger.info(f"Query sent to relay {relay}: {query_ws}")

                async for message in ws:
                    response = json.loads(message)
                    if response[0] == "EVENT" and response[2]["kind"] == 0:
                        event = response[2]
                        event_id = self.calc_event_id(
                            event["pubkey"], event["created_at"], event["kind"], event["tags"], event["content"]
                        )
                        if self.verify_signature(event_id, event["pubkey"], event["sig"]):
                            self.relay_event_pair[relay] = response
                            yield event  # Yield the verified event as it's received
                        break  # Exit after one valid event
        except asyncio.TimeoutError:
            logger.info(f"Timeout waiting for response from {relay}")
            self.unreachable_relays.append(relay)
        except Exception as exc:
            logger.error(f"Error querying {relay}: {exc}")
            self.unreachable_relays.append(relay)

    async def gather_queries(self):
        online_relays = list(self._get_online_relays())  # Convert generator to a list
        tasks = [self.query_relay(relay) for relay in online_relays]

        # Process each task as it's completed
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                yield result  # Yield each verified result

    async def rebroadcast(self, relay):
        try:
            async with websockets.connect(relay) as ws:
                event_json = json.dumps(("EVENT", self.latest_note))
                await ws.send(event_json)
                logger.info(f"Rebroadcasting latest kind 0 event to {relay}")
                response = await ws.recv()
                response_data = json.loads(response)
                logger.debug(f"Relay {relay} returned response {response_data}")
                if str(response_data[2]) in ["true", "True"]:
                    self.updated_relays.append(relay)
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response from {relay}")
            self.bad_relays.append(relay)
        except Exception as exc:
            logger.error(f"Error rebroadcasting to {relay}: {exc}")
            self.bad_relays.append(relay)

    def calculate_latest_event(self, note):
        if note["created_at"] > self.high_time:
            self.high_time = note["created_at"]
            self.latest_note = note

    def calc_old_relays(self):
        logger.info(f"Newest timestamp is: {self.high_time}")
        for relay in self.all_good_relays:
            if self.all_good_relays[relay] < self.high_time:
                logger.debug(f"Relay has old timestamp {relay}: {self.all_good_relays[relay]}")
                self.old_relays.append(relay)

    def integrity_check_whole(self):
        for relay, value in self.relay_event_pair.items():
            note = value[2]
            if note and note["pubkey"] == self.pubkey_to_query and note["kind"] == 0:
                self.good_relays.append(relay)
                self.timestamp_set.add(note["created_at"])
                self.calculate_latest_event(note)
                self.all_good_relays[relay] = note["created_at"]
            else:
                self.bad_relays.append(relay)


@app.post("/updater/scan")
async def handle_pubkey_scan(request: Request):
    data = await request.json()
    pubkey = data.get("pubkey")

    if not pubkey:
        return JSONResponse(content={"error": "pubkey not provided"}, status_code=400)

    updater = NoteUpdater(pubkey)
    updater.process_pubkey()

    async def event_stream():
        async for event in updater.gather_queries():
            updater.integrity_check_whole()
            yield json.dumps({
                "good_relays": updater.good_relays,
                "bad_relays": updater.bad_relays,
                "old_relays": updater.old_relays,
                "updated_relays": updater.updated_relays,
            }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
