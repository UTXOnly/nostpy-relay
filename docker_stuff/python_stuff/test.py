import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from event_handler import app
import psycopg


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_handle_new_event(client):
    # Mock Event class and its methods
    with patch("event_classes.Event") as MockEvent:
        event_instance = MockEvent.return_value
        event_instance.evt_response.return_value = {"results_status": "true"}

        # Mock the database connection and cursor
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_cursor.execute.return_value = None

        with patch(
            "psycopg_pool.AsyncConnectionPool.connection", new_callable=AsyncMock
        ) as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            event_data = {
                "id": "123",
                "pubkey": "pubkey",
                "kind": 0,
                "created_at": 1625152800,
                "tags": [],
                "content": "test content",
                "sig": "signature",
            }

            response = client.post("/new_event", json=event_data)
            assert response.status_code == 200
            assert response.json() == {"results_status": "true"}
            event_instance.add_event.assert_called_once()
            event_instance.evt_response.assert_called_once_with(
                results_status="true", http_status_code=200
            )


@pytest.mark.asyncio
async def test_handle_new_event_duplicate(client):
    with patch("event_classes.Event") as MockEvent:
        event_instance = MockEvent.return_value
        event_instance.evt_response.return_value = {
            "results_status": "false",
            "http_status_code": 409,
            "message": "duplicate: already have this event",
        }

        # Mock the database connection and cursor
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg.IntegrityError()

        with patch(
            "psycopg_pool.AsyncConnectionPool.connection", new_callable=AsyncMock
        ) as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            event_data = {
                "id": "123",
                "pubkey": "pubkey",
                "kind": 0,
                "created_at": 1625152800,
                "tags": [],
                "content": "test content",
                "sig": "signature",
            }

            response = client.post("/new_event", json=event_data)
            assert response.status_code == 409
            assert response.json() == {
                "results_status": "false",
                "http_status_code": 409,
                "message": "duplicate: already have this event",
            }
            event_instance.add_event.assert_called_once()
            event_instance.evt_response.assert_called_once_with(
                results_status="false",
                http_status_code=409,
                message="duplicate: already have this event",
            )


@pytest.mark.asyncio
async def test_handle_new_event_database_error(client):
    with patch("event_classes.Event") as MockEvent:
        event_instance = MockEvent.return_value
        event_instance.evt_response.return_value = {
            "results_status": "false",
            "http_status_code": 400,
            "message": "error: failed to add event",
        }

        # Mock the database connection and cursor
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with patch(
            "psycopg_pool.AsyncConnectionPool.connection", new_callable=AsyncMock
        ) as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            event_data = {
                "id": "123",
                "pubkey": "pubkey",
                "kind": 1,
                "created_at": 1625152800,
                "tags": [],
                "content": "test content",
                "sig": "signature",
            }

            response = client.post("/new_event", json=event_data)
            assert response.status_code == 400
            assert response.json() == {
                "results_status": "false",
                "http_status_code": 400,
                "message": "error: failed to add event",
            }
            event_instance.add_event.assert_called_once()
            event_instance.evt_response.assert_called_once_with(
                results_status="false",
                http_status_code=400,
                message="error: failed to add event",
            )
