import psycopg2

# Define the database connection parameters
conn_params = {
    "host": "localhost",
    "port": "5432",
    "database": "nostr",
    "user": "nostr",
    "password": "nostr"
}

# Define the configuration parameters to set
config_params = {
    "shared_preload_libraries": "pg_stat_statements",
    "track_activity_query_size": "4096",
    "pg_stat_statements.track": "ALL",
    "pg_stat_statements.max": "10000",
    "track_io_timing": "on"
}

# Connect to the database
conn = psycopg2.connect(**conn_params)

# Open a cursor
cur = conn.cursor()

# Loop through the configuration parameters and set them
for param, value in config_params.items():
    query = f"ALTER SYSTEM SET {param} = '{value}'"
    cur.execute(query)

# Commit the changes
conn.commit()

# Close the cursor and connection
cur.close()
conn.close()


# Connect to the chosen database as a superuser (or another user with sufficient permissions)
conn = psycopg2.connect(
    dbname="nostr",
    user="nostr",
    password="nostr",
    host="localhost",
    port="5432"
)

# Create the datadog user
with conn.cursor() as cur:
    cur.execute("CREATE USER datadog WITH password '<PASSWORD>';")

# Set the parameters for postgresql.conf
query = """
    ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
    ALTER SYSTEM SET track_activity_query_size = 4096;
    ALTER SYSTEM SET pg_stat_statements.track = all;
    ALTER SYSTEM SET pg_stat_statements.max = 10000;
    ALTER SYSTEM SET track_io_timing = on;
"""

# Execute the query outside of a transaction
conn.autocommit = True
cur.execute(query)
conn.autocommit = False

# Close the cursor and connection
cur.close()
conn.close()

# Create the function to enable the Agent to collect explain plans
with conn.cursor() as cur:
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

conn.commit()
conn.close()
