import asyncio
import ast
import hashlib
import json
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union


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

    def __init__(self, response_data, logger):
        """
        Initializes the ExtractedResponse object.

        Args:
            response_data (dict): The response data.

        """
        self.logger = logger
        self.event_type = response_data["event"]
        self.subscription_id = response_data["subscription_id"]
        self.message = response_data.get("message", "")
        try:
            self.results = json.loads(response_data["results_json"])
        except json.JSONDecodeError as json_error:
            logger.error(
                f"Error decoding JSON message in Extracted Response: {json_error}."
            )
            self.results = ""

    async def _process_event(self, event_result):
        try:
            self.logger.debug(f"event_result var is {event_result}")
            stripped = str(event_result)[1:-1]
            return ast.literal_eval(stripped)
        except Exception as exc:
            self.logger.error(f"Process events exc is {exc}", exc_info=True)
            return ""

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
                self.message,
            )

        else:
            # Return EOSE
            client_response: Tuple[str, Optional[str]] = (
                self.event_type,
                self.subscription_id,
            )

        return client_response

    async def send_event_loop(self, response_list, websocket) -> None:
        """
        Asynchronously sends a list of event items to a WebSocket.

        Parameters:
            response_list (List[Dict]): A list of dictionaries representing event items.
            websocket (websockets.WebSocketClientProtocol): The WebSocket connection to send the events to.
        """
        tasks = []
        for event_item in response_list:
            task = asyncio.create_task(websocket.send(json.dumps(event_item)))
            tasks.append(task)
        await asyncio.gather(*tasks)


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

    def __init__(self, message: List[Union[str, Dict[str, Any]]], websocket, logger):
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
                merged  
            )
        else:
            self.event_payload: Dict[str, Any] = message[1]
        headers = websocket.request_headers
        self.origin: str = headers.get("origin", "") or headers.get("referer", "")
        self.obfuscate_ip = lambda ip: hashlib.sha256(ip.encode("utf-8")).hexdigest()
        self.obfuscated_client_ip = self.obfuscate_ip("X-Real-IP") or headers.get(
            "X-Forwarded-For"
        )
        logger.debug(f"Client obfuscated IP is {self.obfuscated_client_ip}")
        self.uuid: str = websocket.id
