import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import secp256k1
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional
import uvicorn

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your domain or use ["http://127.0.0.1:8000"]
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (POST, GET, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers
)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    file_path = Path("static/index.html")
    return file_path.read_text()

# In-memory data store for banned and allowed pubkeys and events
banned_pubkeys = ["1234"]
allowed_pubkeys = ["5678"]
banned_events = ["a7561f5aebb4b10c20daa9ce8388ee413b2e7583674a5be25040d5dd9af6a889", "eae7588843b75901433db94db465a5367923bd256af0186f76ae8618db8c7122"]
banned_kinds = ["3","16","17","40","41"]


# Function to decode and validate the Nostr event from the Authorization header
def decode_and_validate_nostr_event(
    auth_header: str, url: str, method: str, body_hash: Optional[str] = None
):
    try:
        if not auth_header.startswith("Nostr "):
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")

        encoded_event = auth_header[len("Nostr ") :]
        decoded_event = base64.b64decode(encoded_event).decode("utf-8")
        nostr_event = json.loads(decoded_event)

        # Check that the event kind is 27235 (NIP-98)
        if nostr_event.get("kind") != 27235:
            raise HTTPException(status_code=401, detail="Invalid event kind")

        # Validate that the "u" tag matches the request URL
        url_tag = next(
            (tag for tag in nostr_event.get("tags", []) if tag[0] == "u"), None
        )
        if not url_tag or url_tag[1] != url:
            raise HTTPException(status_code=401, detail="URL mismatch")

        # Validate that the "method" tag matches the HTTP method
        method_tag = next(
            (tag for tag in nostr_event.get("tags", []) if tag[0] == "method"), None
        )
        if not method_tag or method_tag[1].upper() != method.upper():
            raise HTTPException(status_code=401, detail="HTTP method mismatch")

        # Validate payload hash if provided (for POST/PUT/PATCH)
        if body_hash:
            payload_tag = next(
                (tag for tag in nostr_event.get("tags", []) if tag[0] == "payload"),
                None,
            )
            if not payload_tag or payload_tag[1] != body_hash:
                raise HTTPException(status_code=401, detail="Payload hash mismatch")

        # Verify the event's signature
        pk = nostr_event["pubkey"]
        signature = nostr_event["sig"]
        eid = nostr_event["id"]

        def verify_signature(pubkey, event_id, sig, logger) -> bool:
            try:
                pub_key: secp256k1.PublicKey = secp256k1.PublicKey(
                    bytes.fromhex("02" + pubkey), True
                )
                result: bool = pub_key.schnorr_verify(
                    bytes.fromhex(event_id), bytes.fromhex(sig), None, raw=True
                )
                if result:
                    logger.info(f"Verification successful for event: {event_id}")
                else:
                    logger.error(f"Verification failed for event: {event_id}")
                return result
            except (ValueError, TypeError) as e:
                logger.error(f"Error verifying signature for event {event_id}: {e}")
                return False

        verified = verify_signature(pk, eid, signature, logger)
        if verified:
            return pk
        else:
            return None

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error decoding or validating Nostr event: {e}")
        raise HTTPException(status_code=401, detail="Invalid Nostr event or signature")


# NIP-86 handler with NIP-98 authorization
@app.post("/nip86")
async def nip86_handler(
    request: Request, authorization: Optional[str] = Header(None)
) -> JSONResponse:
    # Validate the Nostr event in the Authorization header
    url = str(request.url)
    method = request.method
    body_hash = None

    if method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()

    pubkey = decode_and_validate_nostr_event(authorization, url, method, body_hash)
    if not pubkey:
        return JSONResponse(
            content={"error": "pubkey verification failed"}, status_code=400
        )

    try:
        # Parse the incoming JSON-RPC-like request
        data = await request.json()
        method = data.get("method")
        params = data.get("params", [])

        # Dispatch the request to the correct NIP-86 method
        if method == "supportedmethods":
            return JSONResponse(
                content={
                    "result": [
                        "banpubkey",
                        "listbannedpubkeys",
                        "allowpubkey",
                        "listallowedpubkeys",
                        "banevent",
                        "allowevent",
                        "changerelayname",
                        "listbannedevents",
                    ]
                }
            )

        elif method == "banpubkey":
            pubkey_to_ban = params[0] if len(params) > 0 else None
            reason = params[1] if len(params) > 1 else None
            if pubkey_to_ban:
                await ban_pubkey(pubkey_to_ban, reason)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing pubkey parameter"}, status_code=400
                )

        elif method == "listbannedpubkeys":
            banned_pubkeys = await list_banned_pubkeys()
            return JSONResponse(content={"result": banned_pubkeys})

        elif method == "allowpubkey":
            pubkey_to_allow = params[0] if len(params) > 0 else None
            reason = params[1] if len(params) > 1 else None
            if pubkey_to_allow:
                await allow_pubkey(pubkey_to_allow, reason)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing pubkey parameter"}, status_code=400
                )

        elif method == "listallowedpubkeys":
            allowed_pubkeys = await list_allowed_pubkeys()
            return JSONResponse(content={"result": allowed_pubkeys})

        elif method == "banevent":
            event_id = params[0] if len(params) > 0 else None
            reason = params[1] if len(params) > 1 else None
            if event_id:
                await ban_event(event_id, reason)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing event ID parameter"}, status_code=400
                )

        elif method == "allowevent":
            event_id = params[0] if len(params) > 0 else None
            reason = params[1] if len(params) > 1 else None
            if event_id:
                await allow_event(event_id, reason)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing event ID parameter"}, status_code=400
                )

        elif method == "listbannedevents":
            banned_events = await list_banned_events()
            return JSONResponse(content={"result": banned_events})

        elif method == "changerelayname":
            new_name = params[0] if len(params) > 0 else None
            if new_name:
                await change_relay_name(new_name)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing relay name parameter"}, status_code=400
                )

        # Add other methods like changerelaydescription, changerelayicon, etc. as needed

        else:
            return JSONResponse(
                content={"error": f"Method {method} not supported"}, status_code=400
            )

    except Exception as exc:
        logger.error(
            f"Exception occurred while handling NIP-86 request: {exc}", exc_info=True
        )
        return JSONResponse(
            content={"error": "An internal error occurred"}, status_code=500
        )


# Method implementations for NIP-86 management tasks


async def ban_pubkey(pubkey: str, reason: str) -> None:
    logger.info(f"Banning pubkey {pubkey} for reason: {reason}")
    banned_pubkeys.append({"pubkey": pubkey, "reason": reason})


async def list_banned_pubkeys() -> List[Dict[str, Any]]:
    logger.info(f"Listing all banned pubkeys")
    return banned_pubkeys


async def allow_pubkey(pubkey: str, reason: str) -> None:
    logger.info(f"Allowing pubkey {pubkey} for reason: {reason}")
    allowed_pubkeys.append({"pubkey": pubkey, "reason": reason})


async def list_allowed_pubkeys() -> List[Dict[str, Any]]:
    logger.info(f"Listing all allowed pubkeys")
    return allowed_pubkeys


async def ban_event(event_id: str, reason: str) -> None:
    logger.info(f"Banning event {event_id} for reason: {reason}")
    banned_events.append({"event_id": event_id, "reason": reason})


async def allow_event(event_id: str, reason: str) -> None:
    logger.info(f"Allowing event {event_id} for reason: {reason}")


async def list_banned_events() -> List[Dict[str, Any]]:
    logger.info(f"Listing all banned events")
    return banned_events


async def change_relay_name(new_name: str) -> None:
    logger.info(f"Changing relay name to: {new_name}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("NIP86_PORT", 8000)))
