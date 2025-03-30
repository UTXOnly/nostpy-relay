import asyncio
import json
import orjson
from typing import List, Tuple, Dict
from fastapi.responses import ORJSONResponse
import secp256k1


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

    def verify_signature(self, logger) -> bool:
        try:
            pub_key: secp256k1.PublicKey = secp256k1.PublicKey(
                bytes.fromhex("02" + self.pubkey), True
            )
            result: bool = pub_key.schnorr_verify(
                bytes.fromhex(self.event_id), bytes.fromhex(self.sig), None, raw=True
            )
            if result:
                logger.info(f"Verification successful for event: {self.event_id}")
            else:
                logger.error(f"Verification failed for event: {self.event_id}")
            return result
        except (ValueError, TypeError) as e:
            logger.error(f"Error verifying signature for event {self.event_id}: {e}")
            return False

    async def delete_check(self, conn, cur) -> None:
        delete_query = """
        DELETE FROM events
        WHERE pubkey = %s AND kind = %s;
        """
        await cur.execute(delete_query, (self.pubkey, self.kind))
        await conn.commit()

    def parse_kind5(self) -> List:
        event_values = [array[1] for array in self.tags]
        return event_values

    async def delete_event(self, conn, cur, delete_events) -> bool:
        delete_statement = """
        DELETE FROM events
        WHERE id = ANY(%s) AND pubkey = %s;
        """
        event_ids = [event_id for event_id in delete_events]
        await cur.execute(delete_statement, (event_ids, self.pubkey))
        await conn.commit()

    async def admin_delete(self, conn, cur, delete_pub):
        delete_statement = """
        DELETE FROM events
        WHERE pubkey = %s;
        """
        await cur.execute(delete_statement, (delete_pub,))
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

    async def add_mgmt_event(self, conn, cur) -> None:
        await cur.execute(
            """
            INSERT INTO event_mgmt (id,pubkey,kind,created_at,tags,content,sig) VALUES (%s, %s, %s, %s, %s, %s, %s)
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

    async def parse_mgmt_event(self, conn, cur):
        for list in self.tags:
            if list[0] == "ban":
                await self.mod_pubkey_perm(conn, cur, list[1], "false", list[2])
                return f"banned: {list[2]} has been banned"
            if list[0] == "allow":
                await self.mod_pubkey_perm(conn, cur, list[1], "true", list[2])
                return f"allowed: {list[2]} has been allowed"

    async def check_mgmt_allow(self, cur) -> bool:
        await cur.execute(
            f"""
            SELECT client_pub FROM allowlist WHERE client_pub = '{self.pubkey}' AND allowed = false;

        """
        )
        return await cur.fetchall()

    async def mod_pubkey_perm(self, conn, cur, conflict_target, bool, conflict_value):
        if conflict_target not in ["client_pub", "kind"]:
            raise ValueError("Invalid conflict target. Must be 'client_pub' or 'kind'.")

        await cur.execute(
            f"""
            INSERT INTO allowlist (note_id, {conflict_target}, allowed) 
            VALUES (%s, %s, %s)
            ON CONFLICT ({conflict_target}) 
            DO UPDATE SET 
                note_id = EXCLUDED.note_id,
                allowed = EXCLUDED.allowed
        """,
            (self.event_id, conflict_value, bool),
        )

        await conn.commit()

    async def check_wot(self, cur):
        await cur.execute(
            f"""
            SELECT pubkey FROM trust_network WHERE pubkey = '{self.pubkey}';
            """
        )
        return await cur.fetchone()

    def evt_response(self, results_status, http_status_code, message=""):
        response = {
            "event": "OK",
            "subscription_id": self.event_id,
            "results_json": results_status,
            "message": message,
        }
        return ORJSONResponse(content=response, status_code=http_status_code)


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
        self.where_clause = ""
        self.column_names = [
            "id",
            "pubkey",
            "kind",
            "created_at",
            "tags",
            "content",
            "sig",
        ]

    def _generate_tag_clause(self, tags) -> str:
        tag_clause = (
            " EXISTS ( SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE {})"
        )
        conditions = [f"elem @> '{tag_pair}'" for tag_pair in tags]

        complete_cluase = tag_clause.format(" OR ".join(conditions))
        return complete_cluase

    def _search_clause(self, search_item):
        search_clause = f" EXISTS ( SELECT 1 FROM jsonb_array_elements(tags) as elem WHERE elem::text ILIKE '%{search_item}%' OR content ILIKE '%{search_item}%')"
        return search_clause

    async def _sanitize_event_keys(self, filters, logger) -> Dict:
        updated_keys = {}
        limit = ""
        global_search = {}
        try:
            logger.debug(f"filters in san is {filters}")
            try:
                limit = filters.get("limit", 100)
                filters.pop("limit")
            except Exception as exc:
                logger.debug(f"Exception is: {exc}")

            try:
                global_search = filters.get("search", {})
                filters.pop("search")
            except Exception as exc:
                logger.debug(f"Exception is: {exc}")

            key_mappings = {
                "authors": "pubkey",
                "kinds": "kind",
                "ids": "id",
            }

            if filters or global_search:
                for key in filters:
                    new_key = key_mappings.get(key, key)
                    if new_key != key:
                        stored_val = filters[key]
                        updated_keys[new_key] = stored_val
                    else:
                        updated_keys[key] = filters[key]

            logger.debug(
                f"updated keys are {updated_keys}, global search is {global_search}"
            )

            return updated_keys, limit, global_search
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return updated_keys, limit, global_search

    async def _parse_sanitized_keys(self, updated_keys, logger) -> Tuple[List, List]:
        query_parts = []
        tag_values = []

        try:
            for item in updated_keys:
                outer_break = False

                if item.startswith("#"):
                    try:
                        for tags in updated_keys[item]:
                            tag_values.append(json.dumps([item[1:], tags]))

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

            return tag_values, query_parts
        except Exception as exc:
            logger.warning(
                f"query not sanitized (maybe empty value) tv is {tag_values}, qp is {query_parts}, error is: {exc}",
                exc_info=True,
            )
            return tag_values, query_parts

    async def _parser_worker(self, record, column_added) -> None:
        row_result = {}
        i = 0
        for item in record:
            row_result[self.column_names[i]] = item
            i += 1
        column_added.append(row_result)

    async def _parser_worker_hard(self, record, column_added) -> None:
        self.hard_col = ["client_pub", "kind", "allowed", "note_id"]
        row_result = {}
        i = 0
        for item in record:
            if item is None:
                row_result[self.hard_col[i]] = "empty"
            elif isinstance(item, bool):
                row_result[self.hard_col[i]] = str(item)
            else:
                row_result[self.hard_col[i]] = item
            i += 1
        column_added.append(row_result)

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

    async def query_result_parser_hard(self, query_result) -> List:
        column_added = []
        try:
            tasks = [
                self._parser_worker_hard(record, column_added)
                for record in query_result
            ]
            await asyncio.gather(*tasks)
            return column_added
        except:
            return None

    def fetch_data_from_cache(self, redis_key, redis_client) -> bytes:
        cached_data = redis_client.get(redis_key)
        if cached_data:
            return cached_data
        else:
            return None

    async def parse_filters(self, filters: dict, logger) -> tuple:
        updated_keys, limit, global_search = await self._sanitize_event_keys(
            filters, logger
        )
        logger.debug(f"Updated keys is: {updated_keys}")
        if updated_keys or global_search:
            tag_values, query_parts = await self._parse_sanitized_keys(
                updated_keys, logger
            )
            return tag_values, query_parts, limit, global_search
        else:
            return {}, {}, None, {}

    def base_query_builder(self, tag_values, query_parts, limit, global_search, logger):
        try:
            if query_parts:
                self.where_clause = " AND ".join(query_parts)

            if tag_values:
                tag_clause = self._generate_tag_clause(tag_values)
                if self.where_clause:
                    self.where_clause += f" AND {tag_clause}"
                else:
                    self.where_clause += f"{tag_clause}"

            if global_search:
                search_clause = self._search_clause(global_search)
                if self.where_clause:
                    self.where_clause += f" AND {search_clause}"
                else:
                    self.where_clause += f"{search_clause}"

            if not limit or limit > 100:
                limit = 100

            self.base_query = f"SELECT * FROM events WHERE {self.where_clause} ORDER BY created_at DESC LIMIT {limit} ;"
            logger.debug(f"SQL query constructed: {self.base_query}")
            return self.base_query
        except Exception as exc:
            logger.error(f"Error building query: {exc}", exc_info=True)
            return None

    def sub_response_builder(
        self, event_type, subscription_id, results_json, http_status_code
    ):
        return ORJSONResponse(
            content={
                "event": event_type,
                "subscription_id": subscription_id,
                "results_json": results_json,
            },
            status_code=http_status_code,
        )
