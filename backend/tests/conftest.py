import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("INIT_ADMIN_USERNAME", "admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "admin123")

from app.main import app
from app.database import init_db, AsyncSessionLocal
from app.auth.bootstrap import bootstrap_admin_user


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    await init_db()
    await bootstrap_admin_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_token(client: AsyncClient):
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    return res.json()["access_token"]
