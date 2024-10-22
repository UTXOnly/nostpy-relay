import psycopg


def initialize_db(logger, write_str) -> None:
    """
    Initialize the database by creating the necessary tables if they don't exist.
    This includes allowed IPs, allowed kinds, and allowed pubkeys with a true/false status and optional reason.
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

            # Index on pubkey and kind columns for events table
            index_columns = ["pubkey", "kind"]
            for column in index_columns:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{str(column)}
                    ON events ({str(column)});
                    """
                )

            # Create allowed IPs table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS allowed_ips (
                    ip_address VARCHAR(255) PRIMARY KEY,
                    allowed BOOLEAN NOT NULL,
                    reason TEXT
                );
                """
            )

            # Create allowed kinds table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS allowed_kinds (
                    kind INTEGER PRIMARY KEY,
                    allowed BOOLEAN NOT NULL,
                    reason TEXT
                );
                """
            )

            # Create allowed pubkeys table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS allowed_pubkeys (
                    pubkey VARCHAR(255) PRIMARY KEY,
                    allowed BOOLEAN NOT NULL,
                    reason TEXT
                );
                """
            )

            conn.commit()
        logger.info("Database initialization complete.")
    except psycopg.Error as caught_error:
        logger.info(f"Error occurred during database initialization: {caught_error}")
