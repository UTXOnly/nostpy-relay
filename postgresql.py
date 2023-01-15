import psycopg2

class PostgresBackend:
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)

    def save_event(self, event: dict):
        # code to save event to Postgres database
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO event (pubkey, kind, payload, created_at) VALUES (%s, %s, %s, %s)",
                (event['pubkey'], event['kind'], json.dumps(event['payload']), event['created_at'])
            )
        self.conn.commit()

    def query_events(self, filter: dict):
        # code to query events from Postgres database
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM event WHERE pubkey = %s AND kind = %s",
                (filter['pubkey'], filter['kind'])
            )
            return cursor.fetchall()

    def delete_event(self, id: str, pubkey: str):
        # code to delete an event from the Postgres database
        with self.conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM event WHERE id = %s AND pubkey = %s",
                (id, pubkey)
            )
        self.conn.commit()
