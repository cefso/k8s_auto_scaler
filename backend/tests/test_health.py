import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_clusters_list(client: AsyncClient, admin_token: str):
    res = await client.get(
        "/api/clusters",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)
