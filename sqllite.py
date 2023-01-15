import sqlite3

class SQLiteBackend:
    def __init__(self, database_path: str):
        self.conn = sqlite3.connect(database_path)

    def save_event(self, event: dict):
        # code to save event to SQLite database
        with self.conn:
            self.conn.execute(
                "INSERT INTO event (pubkey, kind, payload, created_at) VALUES (?, ?, ?, ?)",
                event)
