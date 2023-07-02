import hashlib
import json
import random
import time
import asyncio
import secp256k1
import websockets


# Define the first keypair
public_key1 = "d576043ce19fa2cb684de60ffb8fe529e420a1411b96b6788f11cb0442252eea"
private_key_hex1 = "96f339c05410721070695040a410186de4fdd67714b1e466b97d1aa433707ef6"

# Define the second keypair
public_key2 = "b97b26c3ec44390727b5800598a9de42b222ae7b5402abcf13d2ae8f386e4e0c"
private_key_hex2 = "310cc8246a8bf8d2c9945f255d72272b8d30f86c1e7abac2ad812cb1f1e5a617"

def sign_event_id(event_id: str, private_key_hex: str) -> str:
    private_key = secp256k1.PrivateKey(bytes.fromhex(private_key_hex))
    sig = private_key.schnorr_sign(bytes.fromhex(event_id), bip340tag=None, raw=True)
    return sig.hex()

def calc_event_id(
    public_key: str, created_at: int, kind_number: int, tags: list, content: str
) -> str:
    data = [0, public_key, created_at, kind_number, tags, content]
    data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data_str.encode("UTF-8")).hexdigest()

def create_event(public_key, private_key_hex):
    # Create a list of tags for the event
    tags = []

    words = ["nostr", "so nice", "bless up", "send it", "working?", "the egg", "nip1 FTW", "chillllll", "sooo nice", "eggg", "\U0001F993", "\U0001F596", "\U0001F60F",
         "yolo", "cool beans", "hakuna matata", "let's go", "stay woke", "the bird", "biggie smalls", "Zen mode", "so fresh", "to infinity and beyond", "\U0001F981", "\U0001F4AA", "\U0001F92C",
         "all good", "go with the flow", "shine on", "you got this", "grind time", "the nest", "GOAT status", "just breathe", "vibing out", "sunny side up", "\U0001F423", "\U0001F3B5", "\U0001F64F",
         "mind over matter", "good vibes only", "rise up", "never give up", "hustle & flow", "bird brain", "OG status", "live laugh love", "feeling blessed", "egg-cellent adventure", "\U0001F986", "\U0001F525", "\U0001F601"]


    random_sentence = " ".join([random.choice(words) for i in range(random.randint(3, 6))]).capitalize()

    # Get the current timestamp for the event creation time
    created_at = int(time.time())

    # Calculate the event ID using calc_event_id function
    kind_number = 1
    content = random_sentence
    event_id = calc_event_id(public_key, created_at, kind_number, tags, content)

    # Sign the event ID using sign_event_id function
    signature_hex = sign_event_id(event_id, private_key_hex)

    # Create the event dictionary with all required fields including id and sig
    event_data = {
        "id": event_id,
        "pubkey": public_key,
        "kind": kind_number,
        "created_at": created_at,
        "tags": tags,
        "content": content,
        "sig": signature_hex,
    }

    return event_data

def verify_signature(event_id: str, pubkey: str, sig: str) -> bool:
    try:
        pub_key = secp256k1.PublicKey(bytes.fromhex("02" + pubkey), True)
        result = pub_key.schnorr_verify(bytes.fromhex(event_id), bytes.fromhex(sig), None, raw=True)
        if result:
            print_color(f"Verification successful for event: \033[0m{event_id}\033[0m", 32) # Prints "Verification successful for event " in green, followed by the event id without color
        else:
            print_color(f"Verification failed for event {event_id}", 31) # Prints "verification failed for event " in red
        return result
    except (ValueError, TypeError, secp256k1.Error) as e:
        print_color(f"Error verifying signature for event {event_id}: {e}", 31) # Prints error message in red
        return False

def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")

ws_relay = 'ws://172.28.0.2:8008'

async def send_event(public_key, private_key_hex):
    # Connect to the WebSocket server
    ws_relay = 'ws://172.28.0.2:8008'  # replace with your own websocket URL
    async with websockets.connect(ws_relay) as ws:
        print("WebSocket connection created.")

        for i in range(1):
            # Create a new event
            event_data = create_event(public_key, private_key_hex)
            sig = event_data.get("sig")
            id = event_data.get("id")

            # Verify the event signature
            signature_valid = verify_signature(id, public_key, sig)

            if signature_valid:
                # Serialize the event data to JSON format
                event_json = json.dumps(("EVENT", event_data))

                # Send the event over the WebSocket connection
                await ws.send(event_json)
                print("Event sent:", event_json)
            else:
                print("Invalid signature, event not sent.")

        # Close the WebSocket connection
        print("WebSocket connection closed.")

async def query(ws_relay):
    #ws_relay = 'ws://172.28.0.2:8008'
    ws_relay = 'ws://172.28.0.2:8008'
    async with websockets.connect(ws_relay) as ws:
        print("WebSocket connection created.")

        query_dict = {
            "kinds": [1],
            "limit": 300,
            "since": 1685757900,
            "authors": [
                "b97b26c3ec44390727b5800598a9de42b222ae7b5402abcf13d2ae8f386e4e0c"
            ]
        }

        q = query_dict
        query_ws = json.dumps(("REQ", "5326483051590112", q))
        await ws.send(query_ws)
        #print("Event sent:", query_ws)
        print_color(f"Event sent: \033[0m{query_ws}\033[0m", 32)
        response = await ws.recv()
        print_color(f"Response from websocket server:", 32)
        print_color(f"{response}", 31)
        #return query

async def main():
    while True:
        #event =await send_event(public_key1, private_key_hex1)  # Use the first keypair
        #await asyncio.sleep(20)
        await send_event(public_key2, private_key_hex2)  # Use the second keypair
        await query(ws_relay)
        await asyncio.sleep(10)

asyncio.run(main())


