import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from requests import RequestException
from fastapi.testclient import TestClient
from event_handler import app

class TestEvent(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.environment = {
            'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://opentelemetry-collector:4317',
            'EVENT_HANDLER_PORT': '8000',
            'REDIS_HOST': 'localhost',
            'REDIS_PORT': '6379',
            'PGDATABASE_WRITE': 'write_db',
            'PGUSER_WRITE': 'write_user',
            'PGPASSWORD_WRITE': 'write_password',
            'PGPORT_WRITE': '5432',
            'PGHOST_WRITE': 'localhost',
            'PGDATABASE_READ': 'read_db',
            'PGUSER_READ': 'read_user',
            'PGPASSWORD_READ': 'read_password',
            'PGPORT_READ': '5432',
            'PGHOST_READ': 'localhost'
        }

        # Patch environment variables
        patch.dict('os.environ', self.environment).start()

        # Create a test client for the FastAPI app
        self.client = TestClient(app)

        # Mock Redis and PostgreSQL clients
        self.mock_redis = patch('event_handler.redis.Redis').start()
        self.mock_async_connection_pool = patch('event_handler.AsyncConnectionPool').start()

        # Mock instances for connection pools
        self.mock_write_pool = MagicMock()
        self.mock_read_pool = MagicMock()
        self.mock_async_connection_pool.side_effect = lambda conninfo: self.mock_write_pool if "WRITE" in conninfo else self.mock_read_pool

        # Manually set the connection pools in the app instance
        app.write_pool = self.mock_write_pool
        app.read_pool = self.mock_read_pool

        # Mock the async connection methods
        self.mock_write_conn = AsyncMock()
        self.mock_read_conn = AsyncMock()
        self.mock_write_pool.connection.return_value.__aenter__.return_value = self.mock_write_conn
        self.mock_read_pool.connection.return_value.__aenter__.return_value = self.mock_read_conn

        # Mock the async cursor methods
        self.mock_write_cursor = AsyncMock()
        self.mock_read_cursor = AsyncMock()
        self.mock_write_conn.cursor.return_value.__aenter__.return_value = self.mock_write_cursor
        self.mock_read_conn.cursor.return_value.__aenter__.return_value = self.mock_read_cursor

    def tearDown(self):
        patch.stopall()

    async def test_event_handler_success(self):
        # Setup mock return values
        self.mock_redis.return_value.get.return_value = None
        self.mock_write_cursor.execute.return_value = None
        self.mock_read_cursor.execute.return_value = []

        response = await self.client.post('/new_event', json={
            'id': 'test_id',
            'pubkey': 'test_pubkey',
            'kind': 1,
            'created_at': 123456,
            'tags': [],
            'content': 'test_content',
            'sig': 'test_sig'
        })
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), {
            "event": "OK",
            "subscription_id": "test_id",
            "results_json": "true",
            "message": ""
        })

    async def test_event_handler_failure(self):
        # Setup mock to raise an exception
        self.mock_write_cursor.execute.side_effect = RequestException

        response = self.client.post('/new_event', json={
            'id': 'test_id',
            'pubkey': 'test_pubkey',
            'kind': 1,
            'created_at': 123456,
            'tags': [],
            'content': 'test_content',
            'sig': 'test_sig'
        })
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {
            "event": "OK",
            "subscription_id": "test_id",
            "results_json": "false",
            "message": "error: could not connect to the database"
        })

if __name__ == '__main__':
    unittest.main()
