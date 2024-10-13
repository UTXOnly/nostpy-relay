import psycopg


def initialize_db(logger, write_str) -> None:
    """
    Initialize the database by creating the necessary tables if they don't exist,
    and creating indexes on the pubkey and kind columns.

    """
    try:
        logger.info(f"conn string is {write_str}")
        conn = psycopg.connect(write_str)
        with conn.cursor() as cur:
            # Create events table if it doesn't already exist
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR(255) PRIMARY KEY,
                    pubkey VARCHAR(255),
                    kind INTEGER,
                    created_at INTEGER,
                    tags JSONB,
                    content TEXT,
                    sig VARCHAR(255)
                );
                """
            )

            index_columns = ["pubkey", "kind"]
            for column in index_columns:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{str(column)}
                    ON events ({str(column)});
                    """
                )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS event_mgmt (
                    id VARCHAR(255) PRIMARY KEY,
                    pubkey VARCHAR(255),
                    kind INTEGER,
                    created_at INTEGER,
                    tags JSONB,
                    content TEXT,
                    sig VARCHAR(255)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS allowlist (
                    client_pub VARCHAR(255) UNIQUE,
                    note_id VARCHAR(255),
                    tags JSONB,
                    kind INTEGER UNIQUE,
                    allowed BOOLEAN,
                    sig VARCHAR(255),
                    FOREIGN KEY (note_id) REFERENCES event_mgmt(id)
                );
                """
            )

            conn.commit()
        logger.info("Database initialization complete.")
    except psycopg.Error as caught_error:
        logger.info(f"Error occurred during database initialization: {caught_error}")
