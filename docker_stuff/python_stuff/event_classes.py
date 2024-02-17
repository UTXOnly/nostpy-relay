import asyncio
import json
from typing import List, Tuple, Dict
from fastapi.responses import JSONResponse


class Event:
    """
       Represents an event object with attributes such as event ID, public key, kind, created timestamp, tags, content, and signature.
   
       Attributes:
           event_id (str): The ID of the event.
           pubkey (str): The public key associated with the event.
           kind (int): The type or kind of the event.
           created_at (int): The timestamp when the event was created.
           tags (List): A list of tags associated with the event.
           content (str): The content of the event.
           sig (str): The signature of the event.
   
       Methods:
           delete_check: Checks and deletes the event from the database.
           add_event: Adds the event to the database.
           evt_response: Builds and returns the JSON response for the event.
    """

    def __init__(
        self,
        event_id: str,
        pubkey: str,
        kind: int,
        created_at: int,
        tags: List,
        content: str,
        sig: str,
    ) -> None:
        self.event_id = event_id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.tags = tags
        self.content = content
        self.sig = sig

    def __str__(self) -> str:
        return f"{self.event_id}, {self.pubkey}, {self.kind}, {self.created_at}, {self.tags}, {self.content}, {self.sig} "

    async def delete_check(self, conn, cur, statsd) -> None:
        delete_query = """
        DELETE FROM events
        WHERE pubkey = %s AND kind = %s;
        """
        await cur.execute(delete_query, (self.pubkey, self.kind))
        statsd.decrement("nostr.event.added.count", tags=["func:new_event"])
        statsd.increment("nostr.event.deleted.count", tags=["func:new_event"])
        await conn.commit()

    async def add_event(self, conn, cur) -> None:
        await cur.execute(
            """
            INSERT INTO events (id,pubkey,kind,created_at,tags,content,sig) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                self.event_id,
                self.pubkey,
                self.kind,
                self.created_at,
                json.dumps(self.tags),
                self.content,
                self.sig,
            ),
        )
        await conn.commit()

    async def evt_response(self, results_json, http_status_code):
        response = {
            "event": "OK",
            "subscription_id": "n0stafarian419",
            "results_json": results_json,
        }
        return JSONResponse(content=response, status_code=http_status_code)


class Subscription:
    """
    Represents a subscription object with attributes and methods for handling subscription-related operations.

    Attributes:
        filters (dict): Dictionary containing filters for the subscription.
        subscription_id (str): The ID of the subscription.
        where_clause (str): The WHERE clause of the base SQL query.
        base_query (str): The base SQL query for fetching events.
        column_names (List): List of column names for event attributes.

    Methods:
        generate_tag_clause: Generates the tag clause for SQL query based on given tags.
        sanitize_event_keys: Sanitizes the event keys by mapping and filtering the filters.
        parse_sanitized_keys: Parses and sanitizes the updated keys to generate tag values and query parts.
        generate_query: Generates the SQL query based on provided tags.
        _parser_worker: Worker function to parse and add records to the column.
        query_result_parser: Parses the query result and adds columns accordingly.
        fetch_data_from_cache: Fetches data from cache based on the provided Redis key.
        parse_filters: Parses and sanitizes filters to generate tag values and query parts.
        sub_response_builder: Builds and returns the JSON response for the subscription.
    """

    def __init__(self, request_payload: dict) -> None:
        self.filters = request_payload.get("event_dict", {})
        self.subscription_id = request_payload.get("subscription_id")
        self.where_clause = None
        self.base_query = f"SELECT * FROM events WHERE {self.where_clause};"
        self.column_names = [
            "id",
            "pubkey",
            "kind",
            "created_at",
            "tags",
            "content",
            "sig",
        ]

    async def generate_tag_clause(self, tags) -> str:
        tag_clause = (
            " EXISTS ( SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE {})"
        )
        conditions = [f"elem @> '{json.dumps(tag_pair)}'" for tag_pair in tags]

        complete_query = tag_clause.format(" OR ".join(conditions))
        return complete_query

    async def sanitize_event_keys(self, filters, logger) -> Dict:
        updated_keys = {}
        try:
            
            try:
                # limit_var = filters.get("limit")
                filters.pop("limit")
            except:
                logger.debug(f"No limit")
            # filters["limit"] = min(200, limit_var)
            logger.debug(f"Filters are: {filters}")

            key_mappings = {
                "authors": "pubkey",
                "kinds": "kind",
                "ids": "id",
            }
            
            if len(filters) > 0:
                for key in filters:
                    new_key = key_mappings.get(key, key)
                    if new_key != key:
                        stored_val = filters[key]
                        updated_keys[new_key] = stored_val
                    else:
                        updated_keys[key] = filters[key]

            return updated_keys
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return updated_keys

    async def parse_sanitized_keys(self, updated_keys, logger) -> Tuple[List, List]:
        query_parts = []
        tag_values = []

        try:
            for item in updated_keys:
                outer_break = False

                if item.startswith("#"):
                    try:
                        for tags in updated_keys[item]:
                            tag_values.append(json.dumps([item[1], tags]))

                        outer_break = True
                        continue
                    except TypeError as e:
                        logger.error(f"Error processing tags for key {item}: {e}")

                elif item in ["since", "until"]:
                    if item == "since":
                        since = f'created_at > {updated_keys["since"]}'
                        query_parts.append(since)
                        outer_break = True
                        continue
                    elif item == "until":
                        until = f'created_at < {updated_keys["until"]}'
                        query_parts.append(until)
                        outer_break = True
                        continue

                if outer_break:
                    continue

                array_search = f"{item} = ANY(ARRAY {updated_keys[item]})"
                query_parts.append(array_search)

            logger.debug(f"Returning parse san key {tag_values} and qp: {query_parts}")
            return tag_values, query_parts
        except Exception as exc:
            logger.warning(f"query not sanitized (maybe empty value), error is: {exc}")
            return [], []

    async def generate_query(self, tags) -> str:
        base_query = (
            "EXISTS (SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE {})"
        )
        or_conditions = " OR ".join(f"elem @> '{tag}'" for tag in tags)
        complete_query = base_query.format(or_conditions)
        return complete_query

    async def _parser_worker(self, record, column_added) -> None:
        row_result = {}
        i = 0
        for item in record:
            row_result[self.column_names[i]] = item
            i += 1
        column_added.append([row_result])

    async def query_result_parser(self, query_result) -> List:
        column_added = []
        try:
            tasks = [
                self._parser_worker(record, column_added) for record in query_result
            ]
            await asyncio.gather(*tasks)
            return column_added
        except:
            return None

    async def fetch_data_from_cache(self, redis_key, redis_client) -> bytes:
        cached_data = redis_client.get(redis_key)
        if cached_data:
            return cached_data
        else:
            return None

    async def parse_filters(self, filters: dict, logger) -> tuple:
        updated_keys = await self.sanitize_event_keys(filters, logger)
        logger.debug(f"Updated keys is: {updated_keys}")
        if updated_keys:
            tag_values, query_parts = await self.parse_sanitized_keys(
                updated_keys, logger
            )
        return tag_values, query_parts

    async def sub_response_builder(
        self, event_type, subscription_id, results_json, http_status_code
    ):
        return JSONResponse(
            content={
                "event": event_type,
                "subscription_id": subscription_id,
                "results_json": results_json,
            },
            status_code=http_status_code,
        )
