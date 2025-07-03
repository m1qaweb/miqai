import pytest
from fastapi import FastAPI
from httpx import AsyncClient

@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app instance for testing."""
    app = FastAPI()
    return app

@pytest.fixture
async def async_client(app: FastAPI) -> AsyncClient:
    """Provides an async client for making requests to the app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
