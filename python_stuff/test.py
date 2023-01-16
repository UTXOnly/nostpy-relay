import requests

base_url = 'http://localhost:80'

def post_event(note: dict):
    """
    Sends a POST request to the /event endpoint with the provided nostr note
    """
    response = requests.post(f'{base_url}/event', json=note)
    try:
        response.raise_for_status()
        if response.json():
            return response.json()
        else:
            return response.text
    except requests.exceptions.HTTPError as e:
        return f"HTTP Error: {e}"

def query_events(pubkey: str = None, kind: str = None, payload: dict = None):
    """
    Sends a GET request to the /events endpoint with the provided query parameters
    """
    query_params = {}
    if pubkey:
        query_params['pubkey'] = pubkey
    if kind:
        query_params['kind'] = kind
    if payload:
        query_params['payload'] = payload
    response = requests.get(f'{base_url}/events', params=query_params)
    try:
        response.raise_for_status()
        if response.json():
            return response.json()
        else:
            return response.text
    except requests.exceptions.HTTPError as e:
        return f"HTTP Error: {e}"


note = {
    "pubkey": "example_pubkey",
    "kind": "example_kind",
    "payload": {"example_key": "example_value"}
}


post_response = post_event(note)
print(post_response)

# Query events with only the pubkey parameter
query_response = query_events(pubkey='example_pubkey')
print(query_response)

# Query events with pubkey and kind parameters
query_response = query_events(pubkey='example_pubkey', kind='example_kind')
print(query_response)

# Query events with pubkey, kind, and payload parameters
query_response = query_events(pubkey='example_pubkey', kind='example_kind', payload={"example_key": "example_value"})
print(query_response)



