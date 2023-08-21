import os
import time
from typing import List, Optional
from dotenv import load_dotenv
import psycopg2

load_dotenv()

GREEN = "\033[0;32m"
RED = "\033[0;31m"
RESET = "\033[0m"

class PostgresSetup:

    def __init__(self):
        self.connection_params = {
            'host': os.getenv('POSTGRES_HOST'),
            'port': os.getenv('POSTGRES_PORT'),
            'dbname': os.getenv('POSTGRES_DB'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD')
        }
        self.conn: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> None:
        self.conn = psycopg2.connect(**self.connection_params)

    def disconnect(self) -> None:
        if self.conn:
            self.conn.close()

    def create_datadog_user_and_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname='datadog'")
            exists = cur.fetchone()
            if not exists:
                cur.execute("CREATE USER datadog WITH password 'datadog'")
                print(f"{GREEN}datadog user created in {self.connection_params['dbname']} database{RESET}")
                self.conn.commit()

        with self.conn.cursor() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = 'datadog')")
            schema_exists = cur.fetchone()[0]

        if schema_exists:
            print(f"{RED}datadog schema already exists in {self.connection_params['dbname']} database{RESET}")

        else:
            with self.conn.cursor() as cur:
                cur.execute("CREATE SCHEMA datadog; GRANT USAGE ON SCHEMA datadog TO datadog; GRANT USAGE ON SCHEMA public TO datadog; GRANT pg_monitor TO datadog; CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
                print(f"{GREEN}datadog schema created and permissions granted in {self.connection_params['dbname']} database{RESET}")
                self.conn.commit()

    def explain_statement(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("""
            CREATE OR REPLACE FUNCTION datadog.explain_statement(
                l_query TEXT,
                OUT explain JSON
            )
            RETURNS SETOF JSON AS
            $$
            DECLARE
                curs REFCURSOR;
                plan JSON;
            BEGIN
                OPEN curs FOR EXECUTE pg_catalog.concat('EXPLAIN (FORMAT JSON) ', l_query);
                FETCH curs INTO plan;
                CLOSE curs;
                RETURN QUERY SELECT plan;
            END;
            $$
            LANGUAGE 'plpgsql'
            RETURNS NULL ON NULL INPUT
            SECURITY DEFINER;
            """)
            self.conn.commit()
            time.sleep(2)
        print(f"{GREEN}Explain plans statement completed{RESET}")

    def check_postgres_stats(self) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_stat_database LIMIT 1;")
                print(f"{GREEN}Postgres connection - OK in {self.connection_params['dbname']}")

                cur.execute("SELECT 1 FROM pg_stat_activity LIMIT 1;")
                print(f"{GREEN}Postgres pg_stat_activity read OK in {self.connection_params['dbname']}")

                cur.execute("SELECT 1 FROM pg_stat_statements LIMIT 1;")
                print(f"{GREEN}Postgres pg_stat_statements read OK in {self.connection_params['dbname']}")

            print(f"{RED}\n############### Moving On... to next database ###############################\n{RESET}")
        except psycopg2.OperationalError:
            print(f"{RED}Cannot connect to Postgres database to check stats {self.connection_params['dbname']}{RESET}")
        except psycopg2.Error:
            print(f"{RED}Error while accessing Postgres statistics in {self.connection_params['dbname']}{RESET}")

    def list_databases(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
            databases = [row[0] for row in cur.fetchall() if not row[0].startswith('template')]
        return databases

    def setup_postgres(self) -> None:
        self.connect()
        databases_list = self.list_databases()

        # Iterate through the list of database names, run checks, and create schemas
        for db_name in databases_list:
            print(f"{GREEN}Discovered database: {RESET}{db_name} \nCreating schema and checking permissions + stats")
            self.connection_params['dbname'] = db_name
            self.create_datadog_user_and_schema()
            self.check_postgres_stats()

        print("Setup complete!")

if __name__ == "__main__":
    setup = PostgresSetup()
    setup.setup_postgres()
