import pytest
import pytest_asyncio
from typing import AsyncGenerator
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app

# In-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Sets up an in-memory database and drops it after each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an async httpx client with overridden database dependency."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_artwork_api(monkeypatch):
    """
    Automatically mocks the external artwork API for all tests.
    If artwork_id is 'invalid', raises 404.
    If artwork_id is 'error', raises 502.
    """
    async def mock_fetch(artwork_id: str):
        if artwork_id == "invalid":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Artwork with ID '{artwork_id}' not found in the Art Institute of Chicago API."
            )
        elif artwork_id == "error":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=502,
                detail="Error communicating with the Art Institute of Chicago API."
            )
        return {
            "external_id": artwork_id,
            "title": f"Mock Artwork {artwork_id}",
            "image_id": f"image_uuid_{artwork_id}"
        }
    
    monkeypatch.setattr("app.services.fetch_artwork_from_api", mock_fetch)
