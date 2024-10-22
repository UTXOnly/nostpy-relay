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
from psycopg_pool import AsyncConnectionPool
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import uvicorn
from api_queries import ApiQuery

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_conn_str(db_suffix: str) -> str:
    return (
        f"dbname={os.getenv(f'PGDATABASE_{db_suffix}')} "
        f"user={os.getenv(f'PGUSER_{db_suffix}')} "
        f"password={os.getenv(f'PGPASSWORD_{db_suffix}')} "
        f"host={os.getenv(f'PGHOST_{db_suffix}')} "
        f"port={os.getenv(f'PGPORT_{db_suffix}')} "
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn_str_write = get_conn_str("WRITE")
    conn_str_read = get_conn_str("READ")
    logger.info(f"Write conn string is: {conn_str_write}")
    logger.info(f"Read conn string is: {conn_str_read}")

    app.write_pool = AsyncConnectionPool(conninfo=conn_str_write)
    app.read_pool = AsyncConnectionPool(conninfo=conn_str_read)

    yield

    await app.write_pool.close()
    await app.read_pool.close()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

async def execute_query(app, query_func, *args, **kwargs):
    async with app.read_pool.connection() as conn:
        async with conn.cursor() as cur:
            # Pass the connection, cursor, and any other arguments to the query function
            result = await query_func(conn, cur, *args, **kwargs)
            return result


query_obj = ApiQuery()

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
banned_pubkeys = [{"pubkey": "npub1v02emwxjn2lznkmnszltjy4c7cqzxuejkmye0zeqs62wf0shpahswdmwuj", "reason": "test"}]
allowed_pubkeys = [{"pubkey": "npub1g5pm4gf8hh7skp2rsnw9h2pvkr32sdnuhkcx9yte7qxmrg6v4txqqudjqv", "reason": "admin"}]
banned_events = [{"id": "a7561f5aebb4b10c20daa9ce8388ee413b2e7583674a5be25040d5dd9af6a889", "reason": "spam"}, {"id": "eae7588843b75901433db94db465a5367923bd256af0186f76ae8618db8c7122", "reason": "NSFW"}]
allowed_kinds = ["1","5","2","11"]
blocked_ips = [{"ip": "123.456.789.123", "reason": "spam"}]


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
    
        # Supported Methods List
        if method == "supportedmethods":
            return JSONResponse(
                content={
                    "result": [
                        "banpubkey",
                        "allowpubkey",
                        "listbannedpubkeys",
                        "listallowedpubkeys",
                        "banevent",
                        "allowevent",
                        "listbannedevents",
                        "allowkind",
                        "bankind",
                        "listallowedkinds",
                        "changerelayname",
                        "listblockedips",
                        "blockip",
                        "allowip"
                    ]
                }
            )
    
        # Pubkey Management
        elif method == "banpubkey":
            logger.info(f"Params are {params}")
            pubkey_to_ban = params[0] if len(params) > 0 else None
            reason = params[1] if len(params) > 1 else None
            if pubkey_to_ban:
                await ban_pubkey(pubkey_to_ban, reason)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing pubkey parameter"}, status_code=400
                )
    
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
    
        elif method == "listbannedpubkeys":
            banned_pubkeys = await list_banned_pubkeys()
            return JSONResponse(content={"result": banned_pubkeys})
    
        elif method == "listallowedpubkeys":
            allowed_pubkeys = await list_allowed_pubkeys()
            return JSONResponse(content={"result": allowed_pubkeys})
    
        # Event Management
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
    
        # Kind Management
        elif method == "allowkind":
            kind = int(params[0]) if len(params) > 0 else None
            allowed_kind = await allow_kind(kind)
            if allowed_kind:
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Failed to allow kind"}, status_code=400
                )
    
        elif method == "bankind":
            kind = int(params[0]) if len(params) > 0 else None
            banned_kind = await ban_kind(kind)
            if banned_kind:
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Failed to ban kind"}, status_code=400
                )
    
        elif method == "listallowedkinds":
            allowed = await list_allowed_kinds()
            return JSONResponse(content={"result": allowed})
    
        # IP Management
        elif method == "blockip":
            ip = str(params[0]) if len(params) > 0 else None
            blocked_ip = await block_ip(ip)
            if blocked_ip:
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Failed to block IP"}, status_code=400
                )
    
        elif method == "allowip":
            ip = str(params[0]) if len(params) > 0 else None
            allowed_ip = await allow_ip(ip)
            if allowed_ip:
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Failed to allow IP"}, status_code=400
                )
    
        elif method == "listblockedips":
            blocked_ips = await list_blocked_ips()
            return JSONResponse(content={"result": blocked_ips})
    
        # Relay Management
        elif method == "changerelayname":
            new_name = params[0] if len(params) > 0 else None
            if new_name:
                await change_relay_name(new_name)
                return JSONResponse(content={"result": True})
            else:
                return JSONResponse(
                    content={"error": "Missing relay name parameter"}, status_code=400
                )
    
        # Add other methods like changerelaydescription, changerelayicon, etc.
    
        # Fallback for unsupported methods
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

async def execute_query(self, app, query_func, *args, **kwargs):
    async with app.write_pool.connection() as conn:
        async with conn.cursor() as cur:
            # Pass the connection, cursor, and any other arguments to the query function
            result = await query_func(conn, cur, *args, **kwargs)
            return result

# Method implementations for NIP-86 management tasks
#class QueryMethods:

    # Pubkey Management
async def ban_pubkey(pubkey: str, reason: str) -> None:
    logger.info(f"Banning pubkey {pubkey} for reason: {reason}")
    banned_pubkeys.append({"pubkey": pubkey, "reason": reason})
    banned_pubkey = await execute_query(app, query_obj.insert_pubkey_list, pubkey, False, reason, logger)


async def allow_pubkey(pubkey: str, reason: str) -> None:
    logger.info(f"Allowing pubkey {pubkey} for reason: {reason}")
    allowed_pubkeys.append({"pubkey": pubkey, "reason": reason})


async def list_banned_pubkeys() -> List[Dict[str, Any]]:
    logger.info(f"Listing all banned pubkeys")
    return banned_pubkeys


async def list_allowed_pubkeys() -> List[Dict[str, Any]]:
    logger.info(f"Listing all allowed pubkeys")
    return allowed_pubkeys


# Event Management
async def ban_event(event_id: str, reason: str) -> None:
    logger.info(f"Banning event {event_id} for reason: {reason}")
    banned_events.append({"event_id": event_id, "reason": reason})


async def allow_event(event_id: str, reason: str) -> None:
    logger.info(f"Allowing event {event_id} for reason: {reason}")


async def list_banned_events() -> List[Dict[str, Any]]:
    logger.info(f"Listing all banned events")
    return banned_events


# Kind Management
async def allow_kind(kind: int) -> bool:
    logger.info(f"Allowed kind: {kind} and type: {type(kind)}")
    if isinstance(kind, int):
        allowed_kinds.append(kind)
        return True
    else:
        return False


async def ban_kind(kind: int) -> bool:
    logger.info(f"Banned kind: {kind}")
    if isinstance(kind, int) and kind in allowed_kinds:
        allowed_kinds.pop(kind)
        return True
    else:
        return False


async def list_allowed_kinds() -> List[Dict[str, Any]]:
    logger.info(f"Listing all allowed kinds")
    return allowed_kinds


# IP Management
async def block_ip(ip: str) -> bool:
    logger.info(f"Banning IP: {ip}")
    if isinstance(ip, str):
        blocked_ips.append(ip)
        return True
    else:
        return False


async def allow_ip(ip: str) -> bool:
    logger.info(f"Allowing IP: {ip}")
    if isinstance(ip, str):
        blocked_ips.append(ip)
        return True
    else:
        return False


async def list_blocked_ips() -> List[Dict[str, Any]]:
    logger.info(f"Listing blocked ips")
    return blocked_ips


# Relay Management
async def change_relay_name(new_name: str) -> None:
    logger.info(f"Changing relay name to: {new_name}")
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", 8000)))
