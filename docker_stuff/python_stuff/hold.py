import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Tuple, Optional, List, Dict, Any

executor = ThreadPoolExecutor()


async def format_response(
    self,
) -> Union[
    Tuple[str, Optional[str], str, Optional[str]],
    List[Tuple[str, Optional[str], Dict[str, Any]]],
    Tuple[str, Optional[str]],
]:
    """
    Formats the response based on the event type.

    Returns:
        Union[Tuple[str, Optional[str], str, Optional[str]], List[Tuple[str, Optional[str], Dict[str, Any]]], Tuple[str, Optional[str]]]: The formatted response.
    """
    if self.event_type == "EVENT":
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(executor, self._process_event, event_result)
            for event_result in self.results
        ]
        parsed_results = await asyncio.gather(*tasks)
        events_to_send = [
            (self.event_type, self.subscription_id, result) for result in parsed_results
        ]
        return events_to_send
    elif self.event_type == "OK":
        return (self.event_type, self.subscription_id, self.results, self.message)
    else:
        # Return EOSE
        return (self.event_type, self.subscription_id)


async def send_event_loop(self, response_list: List[Dict[str, Any]], websocket) -> None:
    """
    Asynchronously sends a list of event items to a WebSocket.

    Parameters:
        response_list (List[Dict]): A list of dictionaries representing event items.
        websocket (websockets.WebSocketClientProtocol): The WebSocket connection to send the events to.
    """
    try:
        await asyncio.gather(
            *(websocket.send(json.dumps(event_item)) for event_item in response_list)
        )
    except Exception as e:
        logger.error(f"Error in send_event_loop: {e}")
        raise
