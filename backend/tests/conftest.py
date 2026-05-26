import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DEBUG", "true")

from app.main import app
from app.database import init_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
