import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_fail(client: AsyncClient):
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_clusters_require_auth(client: AsyncClient):
    res = await client.get("/api/clusters")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_clusters_with_token(client: AsyncClient, admin_token: str):
    res = await client.get("/api/clusters", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_invalid_cron_rejected(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.post(
        "/api/scaling/schedules",
        headers=headers,
        json={
            "cluster_id": 1,
            "namespace": "default",
            "resource_type": "Deployment",
            "resource_name": "test",
            "target_replicas": 1,
            "cron_expression": "not a cron",
        },
    )
    assert res.status_code == 422
