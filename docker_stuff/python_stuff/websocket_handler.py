import hashlib
import json
import logging
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple, Union
import time

import aiohttp
import asyncio
import websockets
from datadog import initialize, statsd
from ddtrace import tracer


import websockets.exceptions
from aiohttp.client_exceptions import ClientConnectionError

options: Dict[str, Any] = {"statsd_host": "172.28.0.5", "statsd_port": 8125}

initialize(**options)

tracer.configure(hostname="172.28.0.5", port=8126)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file: str = "./logs/websocket_handler.log"
handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class TokenBucketRateLimiter:
    """
    A class representing a token bucket rate limiter.

    Attributes:
        tokens_per_second (int): The number of tokens allowed per second.
        max_tokens (int): The maximum number of tokens in the bucket.
        tokens (defaultdict): A dictionary storing the current number of tokens for each client.
        last_request_time (defaultdict): A dictionary storing the timestamp of the last request for each client.

    Methods:
        _get_tokens(client_id: str) -> None: Updates the number of tokens for a given client based on the time passed since the last request.
        _parse_token_count(token_count: str) -> dict: Parses a string representation of token count into a dictionary.
        __str__() -> str: Returns a string representation of the current token counts.
        check_request(client_id: str) -> bool: Checks if a request from a client is allowed based on the available tokens.

    """

    def __init__(self, tokens_per_second: int, max_tokens: int):
        """
        Initializes the TokenBucketRateLimiter object.

        Args:
            tokens_per_second (int): The number of tokens allowed per second.
            max_tokens (int): The maximum number of tokens in the bucket.

        """
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = defaultdict(lambda: self.max_tokens)
        self.last_request_time = defaultdict(lambda: 0)

    async def _get_tokens(self, client_id: str) -> None:
        """
        Updates the number of tokens for a given client based on the time passed since the last request.

        Args:
            client_id (str): The ID of the client.

        Returns:
            None

        """
        current_time = time.time()
        time_passed = current_time - self.last_request_time[client_id]
        new_tokens = int(time_passed * self.tokens_per_second)
        self.tokens[client_id] = min(
            self.tokens[client_id] + new_tokens, self.max_tokens
        )
        self.last_request_time[client_id] = current_time
        return self.tokens

    def _parse_token_count(self, token_count: str) -> dict:
        """
        Parses a string representation of token count into a dictionary.

        Args:
            token_count (str): The string representation of token count.

        Returns:
            dict: The parsed token count as a dictionary.

        """
        start_index = token_count.find("{") + 1
        end_index = token_count.find("}")
        dictionary_str = token_count[start_index:end_index]
        dictionary_splitter = dictionary_str.split(",")
        dictionary = {}
        for item in dictionary_splitter:
            key, value = item.split(":")
            dictionary[key.strip()] = int(value.strip())
        return dictionary

    def __str__(self):
        """
        Returns a string representation of the current token counts.

        Returns:
            str: The string representation of the current token counts.

        """
        return str(dict(self.tokens))

    async def check_request(self, client_id: str) -> bool:
        """
        Checks if a request from a client is allowed based on the available tokens.

        Args:
            client_id (str): The ID of the client.

        Returns:
            bool: True if the request is allowed, False otherwise.

        """
        await self._get_tokens(client_id)
        if self.tokens[client_id] >= 1:
            self.tokens[client_id] -= 1
            return True
        return False


class ExtractedResponse:
    """
    A class representing an extracted response.

    Attributes:
        event_type (str): The type of the response event.
        subscription_id (str): The subscription ID associated with the response.
        results (Any): The response data.
        comment (str): Additional comment for the response.
        rate_limit_response (Tuple[str, Optional[str], str, Optional[str]]): Rate limit response tuple.
        duplicate_response (Tuple[str, Optional[str], str, Optional[str]]): Duplicate response tuple.

    Methods:
        format_response(): Formats the response based on the event type.

    """

    def __init__(self, response_data):
        """
        Initializes the ExtractedResponse object.

        Args:
            response_data (dict): The response data.

        """
        self.event_type = response_data["event"]
        self.subscription_id = response_data["subscription_id"]
        try:
            self.results = json.loads(response_data["results_json"])
        except json.JSONDecodeError as json_error:
            logger.error(
                f"Error decoding JSON message in Extracted REsponse: {json_error}"
            )
            self.results = ""

        self.comment = ""
        self.rate_limit_response: Tuple[str, Optional[str], str, Optional[str]] = (
            "OK",
            "nostafarian419",
            "false",
            "rate-limited: slow your roll nostrich",
        )
        self.duplicate_response: Tuple[str, Optional[str], str, Optional[str]] = (
            "OK",
            "nostafarian419",
            "false",
            "duplicate: already have this event",
        )

    #
    async def _process_event(self, event_result):
        try:
            stripped = str(event_result)[1:-1]
            logger.info(f"Stripped var is {stripped} and of type : {type(stripped)}")
            # return json.loads(stripped)
            stripped = stripped.replace("'", '"')
            logger.debug(f"Returning stripped {stripped}")
            return json.loads(stripped)
        except Exception as exc:
            logger.error(f"Process events exc is {exc}", exc_info=True )
            return ""
        # return ast.literal_eval(stripped)

    async def format_response(self):
        """
        Formats the response based on the event type.

        Returns:
            Union[Tuple[str, Optional[str], str, Optional[str]], List[Tuple[str, Optional[str], Dict[str, Any]]], Tuple[str, Optional[str]]]: The formatted response.

        """
        if self.event_type == "EVENT":
            tasks = [self._process_event(event_result) for event_result in self.results]
            parsed_results = await asyncio.gather(*tasks)
            events_to_send = [
                (self.event_type, self.subscription_id, result)
                for result in parsed_results
            ]
            return events_to_send
        elif self.event_type == "OK":
            client_response: Tuple[str, Optional[str], str, Optional[str]] = (
                self.event_type,
                self.subscription_id,
                self.results,
                self.comment,
            )

        else:
            # Return EOSE
            client_response: Tuple[str, Optional[str]] = (
                self.event_type,
                self.subscription_id,
            )

        return client_response


class WebsocketMessages:
    """
    A class representing WebSocket messages.

    Attributes:
        event_type (str): The type of the WebSocket event.
        subscription_id (str): The subscription ID associated with the event.
        event_payload (Union[List[Dict[str, Any]], Dict[str, Any]]): The payload of the event.
        origin (str): The origin or referer of the WebSocket request.
        obfuscate_ip (function): A lambda function to obfuscate the client IP address.
        obfuscated_client_ip (str): The obfuscated client IP address.
        uuid (str): The unique identifier of the WebSocket connection.

    Methods:
        __init__(self, message: List[Union[str, Dict[str, Any]]], websocket): Initializes the WebSocketMessages object.

    """

    def __init__(self, message: List[Union[str, Dict[str, Any]]], websocket):
        """
        Initializes the WebSocketMessages object.

        Args:
            message (List[Union[str, Dict[str, Any]]]): The WebSocket message.
            websocket: The WebSocket connection.

        """
        self.event_type = message[0]
        if self.event_type in ("REQ", "CLOSE"):
            self.subscription_id: str = message[1]
            logger.debug(f"Message is {message} and of type {type(message)}")
            raw_payload = message[2:]
            logger.debug(f"Raw payload is {raw_payload} and len {len(raw_payload)}")
            merged = {}
            for item in raw_payload:
                merged.update(item)
            logger.debug(f"merged is {merged} and type {type(merged)}")
            self.event_payload = (
                merged  # {json.loads(item) for item in range(2, len(message))}
            )
        else:
            self.event_payload: Dict[str, Any] = message[1]
        headers: websockets.Headers = websocket.request_headers
        self.origin: str = headers.get("origin", "") or headers.get("referer", "")
        self.obfuscate_ip = lambda ip: hashlib.sha256(ip.encode("utf-8")).hexdigest()
        self.obfuscated_client_ip = self.obfuscate_ip("X-Real-IP") or headers.get(
            "X-Forwarded-For"
        )
        logger.debug(f"Client obfuscated IP is {self.obfuscated_client_ip}")
        self.uuid: str = websocket.id


unique_sessions = []
client_ips = []




async def handle_websocket_connection(
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    global unique_sessions, client_ips
    conn = aiohttp.TCPConnector(limit=500)
    # Create a single aiohttp session per WebSocket connection
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            async for message in websocket:
                try:
                    logger.debug(f"message in loop is {message}")
                    ws_message = message
                    if len(ws_message) > 0:
                        ws_message = WebsocketMessages(
                            message=json.loads(message), websocket=websocket
                        )
                except json.JSONDecodeError as json_error:
                    logger.error(f"Error decoding JSON message: {json_error}")
                    continue  # Skip processing this message

                logger.debug(f"UUID = {ws_message.uuid}")
                statsd.increment(
                    "nostr.new_connection.count",
                    tags=[
                        f"client_ip:{ws_message.obfuscated_client_ip}",
                        f"nostr_client:{ws_message.origin}",
                    ],
                )
                logger.debug(f"WS event payload is {ws_message.event_payload}")
                if ws_message.event_type == "EVENT":
                    logger.debug(
                        f"Event to be sent payload is: {ws_message.event_payload} of type {type(ws_message.event_payload)}"
                    )
                    await send_event_to_handler(
                        session=session,
                        event_dict=dict(ws_message.event_payload),
                        websocket=websocket,
                    )
                elif ws_message.event_type == "REQ":
                    logger.debug(f"Entering REQ branch")
                    logger.debug(
                        f"Payload is {ws_message.event_payload} and of type: {type(ws_message.event_payload)}"
                    )
                    await send_subscription_to_handler(
                        session=session,
                        event_dict=ws_message.event_payload,
                        subscription_id=ws_message.subscription_id,
                        websocket=websocket,
                    )
                elif ws_message.event_type == "CLOSE":
                    response: Tuple[str, str] = (
                        "NOTICE",
                        f"closing {ws_message.subscription_id}",
                    )
                    await websocket.send(json.dumps(response))

        except websockets.exceptions.ConnectionClosedError as close_error:
            logger.error(
                f"WebSocket connection closed unexpectedly: {close_error}",
                exc_info=True,
            )


        except ClientConnectionError as connection_error:
            logger.error(
                f"Connection error occurred: {connection_error}", exc_info=True
            )


        except aiohttp.ClientError as client_error:
            logger.error(f"HTTP client error occurred: {client_error}", exc_info=True)


        except Exception as e:
            logger.error(
                f"Error occurred while processing WebSocket message: {e}", exc_info=True
            )



async def send_event_to_handler(
    session: aiohttp.ClientSession,
    event_dict: Dict[str, Any],
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    url: str = "http://event_handler/new_event"
    try:
        async with session.post(url, data=json.dumps(event_dict)) as response:
            logger.debug(f"Response event handler variable is {response}")
            response_data: Dict[str, Any] = await response.json()
            logger.debug(
                f"Received response from Event Handler {response_data}, data types is {type(response_data)}"
            )
            response_object = ExtractedResponse(response_data)
            if response.status == 200:
                formatted_response = await response_object.format_response()
                logger.debug(
                    f"Formatted response data from send_event_to_handler function: {formatted_response}"
                )
                await websocket.send(json.dumps(formatted_response))
            elif response.status == 409:
                return response_object.duplicate_response
    except Exception as e:
        logger.error(f"An error occurred while sending the event to the handler: {e}")


async def send_event_loop(response_list, websocket):
    tasks = []

    for event_item in response_list:
        logger.debug(f"Final response from REQ to ws client: {event_item}")
        task = asyncio.create_task(websocket.send(json.dumps(event_item)))
        tasks.append(task)

    await asyncio.gather(*tasks)


async def send_subscription_to_handler(
    session: aiohttp.ClientSession,
    event_dict: Dict,
    subscription_id: str,
    websocket: websockets.WebSocketServerProtocol,
) -> None:
    url: str = "http://event_handler/subscription"
    payload: Dict[str, Any] = {
        "event_dict": event_dict,
        "subscription_id": subscription_id,
    }

    async with session.post(url, data=json.dumps(payload)) as response:
        response_data = await response.json()
        logger.debug(
            f"Data type of response_data: {type(response_data)}, Response Data: {response_data}"
        )
        if not response_data:
            logger.debug("Response data none, returning")
            await websocket.send(json.dumps(["EOSE", subscription_id]))
            return
        response_object = ExtractedResponse(response_data=response_data)

        logger.debug(f"Response received as: {response_data}")
        EOSE: Tuple[str, Optional[str]] = "EOSE", response_object.subscription_id

        if response.status == 200 and response_object.event_type == "EVENT":
            response_list = await response_object.format_response()
            logger.debug(f"Response list is : {response_list}")
            await send_event_loop(response_list, websocket)
            await websocket.send(json.dumps(EOSE))
        else:
            await websocket.send(json.dumps(EOSE))
            await websocket.send(json.dumps("CLOSED", subscription_id, "I don't have any response"))
            logger.debug(f"Response data is {response_data} but it failed")


if __name__ == "__main__":
    # gitrate_limiter = TokenBucketRateLimiter(tokens_per_second=1, max_tokens=30000)

    try:
        start_server = websockets.serve(handle_websocket_connection, "0.0.0.0", 8008)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

    except Exception as e:
        logger.error(f"Error occurred while starting the server main loop: {e}")
