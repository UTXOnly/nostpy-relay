import asyncio
import ast
import gc
import json
import logging
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
import websockets
from asyncpg import create_pool




logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class NostrFollowFetcher:
    def __init__(self, pubkey, db_conn_str, seed_relays, min_followers=1, sleep_time=5):
        self.pubkey = pubkey
        self.db_conn_str = db_conn_str
        self.min_followers = min_followers
        self.seed_relays = seed_relays
        self.pubkey_follower_count = defaultdict(int)
        self.trust_network = set()
        self.db_pool = None
        self.admin_follow_list = []
        self.sleep_time = (
            sleep_time  # Time to sleep between scans to avoid rate limiting
        )

    async def init_db(self):
        self.db_pool = await create_pool(self.db_conn_str)
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS follows (
                    pubkey TEXT PRIMARY KEY,
                    followed_pubkey_list JSONB
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trust_network (
                    pubkey TEXT PRIMARY KEY
                )
            """
            )

    async def connect_to_relay(self, relay_url, pubkey):
        try:
            async with websockets.connect(relay_url) as websocket:
                message = await self.subscribe_to_follows(websocket, pubkey)

                if message:
                    try:
                        message_data = ast.literal_eval(str(message))

                        if (
                            isinstance(message_data, list)
                            and message_data[0] == "EVENT"
                        ):
                            event_data = message_data[2]
                            await self.handle_event(event_data)
                        else:
                            pass
                    except (IndexError, KeyError, ValueError) as e:
                        logger.error(f"Error processing message from {relay_url}: {e}")
                else:
                    logger.warning(f"No message received from {relay_url}, moving on.")
        except Exception as e:
            logger.error(f"Error connecting to relay {relay_url}: {e}")

    async def subscribe_to_follows(self, websocket, pubkey, timeout=4):
        subscription_filter = {
            "kinds": [3],
            "authors": [pubkey],
        }
        request = ["REQ", "subscription_id", subscription_filter]
        await websocket.send(json.dumps(request))

        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            return message
        except asyncio.TimeoutError:
            logger.error(f"Timeout reached after {timeout} seconds, closing connection.")
            return None

    async def handle_event(self, event):
        l1_follow_list = []
        if event["kind"] == 3:
            follows = event.get("tags", [])
            for follow in follows:
                if follow[0] == "p":
                    followed_pubkey = follow[1]
                    l1_follow_list.append(followed_pubkey)

        await self.store_follow_in_db(event["pubkey"], l1_follow_list)

        if event["pubkey"] == self.pubkey:
            self.admin_follow_list = l1_follow_list

    async def scan_l1_follows(self, l1_follow_list):
        logger.debug(f"L1 follow list is {l1_follow_list}")

        tasks = []
        for pubkey in l1_follow_list:
            for relay_url in self.seed_relays:
                tasks.append(self.connect_to_relay(relay_url, pubkey))

        batch_size = 50
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]  # Get a batch of 50 tasks
            await asyncio.gather(*batch)  # Run the batch of tasks concurrently
            await asyncio.sleep(
                self.sleep_time
            )  # Sleep between batches to avoid rate limiting

        logger.info(f"Completed scanning for all L1 followers.")

    async def store_follow_in_db(self, pubkey, followed_pubkey_list):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO follows (pubkey, followed_pubkey_list)
                VALUES ($1, $2)
                ON CONFLICT (pubkey) DO UPDATE
                SET followed_pubkey_list = EXCLUDED.followed_pubkey_list
            """,
                pubkey,
                json.dumps(followed_pubkey_list),
            )

    async def get_common_followers(self):
        async with self.db_pool.acquire() as conn:
            pubkey_list = [self.pubkey] + self.admin_follow_list

            result = await conn.fetch(
                """
                WITH follower_counts AS (
                    SELECT
                        jsonb_array_elements(followed_pubkey_list) AS pubkey
                    FROM
                        follows
                    WHERE
                        pubkey = ANY($1::text[])  
                )
                SELECT
                    pubkey,
                    COUNT(pubkey) AS follow_count
                FROM
                    follower_counts
                GROUP BY
                    pubkey
                HAVING
                    COUNT(pubkey) >= 3;  
            """,
                pubkey_list,
            )

            common_followers = [row["pubkey"].strip('"') for row in result]
            logger.debug(
                f"Public keys followed by you and at least 2 other followers: {common_followers}"
            )

            return common_followers

    async def add_to_trust_network(self, com_followers):
        async with self.db_pool.acquire() as conn:
            for pubkey in com_followers:
                await conn.execute(
                    """
                    INSERT INTO trust_network (pubkey)
                    VALUES ($1)
                    ON CONFLICT DO NOTHING
                """,
                    pubkey,
                )

    async def run(self):
        await self.init_db()

        tasks = [
            self.connect_to_relay(relay_url, self.pubkey)
            for relay_url in self.seed_relays
        ]
        await asyncio.gather(*tasks)

        await self.scan_l1_follows(self.admin_follow_list)

        common_follows = await self.get_common_followers()
        await self.add_to_trust_network(common_follows)


if __name__ == "__main__":
    seed_relays = [
        "wss://nos.lol",
        "wss://nostr.mom",
        "wss://purplepag.es",
        "wss://relay.damus.io",
    ]
    dotenv_path = os.path.expanduser("~/nostpy-relay/docker/.env")
    load_dotenv(dotenv_path)
    db_conn_str = os.getenv("DB_CONN_STRING")
    pubkey = os.getenv("ADMIN_PUBKEY")


    fetcher = NostrFollowFetcher(
        pubkey=pubkey, db_conn_str=db_conn_str, seed_relays=seed_relays
    )
    asyncio.run(fetcher.run())
