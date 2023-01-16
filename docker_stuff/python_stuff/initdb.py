from os import environ as os
from sqlalchemy import create_engine, text

database_url = os.environ.get("DATABASE_URL")

class PostgresBackend:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)

    def init(self):
        try:
            with self.engine.connect() as conn:
                # Create the tags_to_tagvalues function
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION tags_to_tagvalues(jsonb) 
                    RETURNS text[] AS $$
                    SELECT array_agg(t->>1) FROM (SELECT jsonb_array_elements($1) AS t)s WHERE length(t->>0) = 1;
                    $$ LANGUAGE SQL IMMUTABLE RETURNS NULL ON NULL INPUT;
                """))

                # Create the event table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS event (
                      id text NOT NULL,
                      pubkey text NOT NULL,
                      created_at integer NOT NULL,
                      kind integer NOT NULL,
                      tags jsonb NOT NULL,
                      content text NOT NULL,
                      sig text NOT NULL,

                      tagvalues text[] GENERATED ALWAYS AS (tags_to_tagvalues(tags)) STORED
                    );
                """))

                # Create indexes
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ididx ON event USING btree (id text_pattern_ops);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS pubkeyprefix ON event USING btree (pubkey text_pattern_ops);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS timeidx ON event (created_at);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS kindidx ON event (kind);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS arbitrarytagvalues ON event USING gin (tagvalues);"))

        except Exception as error:
            print("Error while connecting to PostgreSQL", error)
            return error
