"""Test fixtures — in-memory SQLite database for API integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# Register custom type compiles for SQLite compatibility
# pgvector's Vector and PostgreSQL's TSVECTOR don't exist in SQLite
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
    from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
    from sqlalchemy.ext.compiler import compiles

    @event.listens_for(Base.metadata, "before_create")
    def _remap_pg_types(target, connection, **kw):
        """No-op — type compilation handles this."""

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_, compiler, **kw):
        return "TEXT"

    @compiles(type(TSVECTOR()), "sqlite")  # noqa: E721
    def _compile_tsvector_sqlite(type_, compiler, **kw):
        return "TEXT"

except ImportError:
    pass


# In-memory SQLite engine for tests
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db():
    async with TestSession() as session:
        yield session


# Override the database dependency
app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
