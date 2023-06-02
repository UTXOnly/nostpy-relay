import secp256k1
import hashlib
import json
import binascii
import random
import time
import websocket


# Define public and private keys
public_key = "0c4a687a4414e30b43a94e1492391512019e52c5cceaf87d81358fb6e238780a"
private_key_hex = "71537cbf6585e194a836cc049a7094d5bc253f23bb6abf980624575d84b127b9"

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


def create_event():
    # Create a list of tags for the event
    tags = []

    # Generate a random sentence for the event content
    words = ["nostr", "so nice", "bless up", "send it", "working?", "the egg", "nip1 FTW", "chillllll", "sooo nice", "eggg", "\U0001F993", "\U0001F596", "\U0001F60F" ]
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



def send_event():
    # Connect to the WebSocket server
    ws_relay = 'wss://nostpy.lol' # replace with your own websocket URL
    ws = websocket.create_connection(ws_relay)
    print("WebSocket connection created.")

    for i in range(100):
        # Create a new event
        event_data = create_event()
        sig = event_data.get("sig")
        id = event_data.get("id")

        # Verify the event signature
        signature_valid = verify_signature(id, public_key, sig)

        if signature_valid:
            # Serialize the event data to JSON format
            event_json = json.dumps(("EVENT", event_data))

            # Send the event over the WebSocket connection
            ws.send(event_json)
            print("Event sent:", event_json)
        else:
            print("Invalid signature, event not sent.")

    # Close the WebSocket connection
    ws.close()
    print("WebSocket connection closed.")

send_event()
