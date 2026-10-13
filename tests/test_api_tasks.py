"""Tests for FastAPI task endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_and_get_task():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit task
        payload = {
            "prompt": "Create a page called 'Research Overview'",
            "notify_channels": ["notion_comment"],
            "mode": "auto",
        }
        create_res = await client.post("/tasks", json=payload)
        assert create_res.status_code == 202
        data = create_res.json()
        task_id = data["task_id"]
        assert task_id is not None

        # Retrieve task
        get_res = await client.get(f"/tasks/{task_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["task_id"] == task_id
        assert get_data["prompt"] == payload["prompt"]


@pytest.mark.asyncio
async def test_idempotency_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        idem_key = "test-idem-unique-12345"
        payload = {
            "prompt": "Create meeting notes page",
            "idempotency_key": idem_key,
        }
        res1 = await client.post("/tasks", json=payload)
        task_id_1 = res1.json()["task_id"]

        # Second request with same idempotency key
        res2 = await client.post("/tasks", json=payload)
        task_id_2 = res2.json()["task_id"]

        # Must return the same task_id
        assert task_id_1 == task_id_2
