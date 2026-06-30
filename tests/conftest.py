"""
tests/conftest.py — DropKey v3.2 Test Configuration & Fixtures

Provides:
- Database setup/teardown
- Session management
- Mock objects
- Test data factories
- Async support
"""

import asyncio
import os
from typing import AsyncGenerator
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient

# ═════════════════════════════════════════════════════════════════════════════
# PYTEST CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

# Enable pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# Set asyncio mode
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ═════════════════════════════════════════════════════════════════════════════
# DATABASE FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def test_db():
    """
    Create test database in memory.
    
    Uses SQLite in-memory database for fast tests.
    Automatically creates and drops tables.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Import models to register with Base
    from models import Base
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Yield session
    async with session_factory() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_db):
    """Get database session for tests."""
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    from config import Settings
    
    return Settings(
        environment="testing",
        debug=True,
        app_name="DropKey Test",
        app_version="3.2.0",
        host="127.0.0.1",
        port=8000,
        log_level="DEBUG",
        database_enabled=True,
        jwt_enabled=True,
        jwt_secret_key="test-secret-key-minimum-32-characters-long",
        jwt_algorithm="HS256",
        rate_limiting_enabled=False,  # Disable for tests
        cors_enabled=True,
    )


@pytest.fixture
async def client(mock_settings):
    """
    Create async test client for API testing.
    
    Returns AsyncClient configured for the test app.
    """
    from main import app
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ═════════════════════════════════════════════════════════════════════════════
# REPOSITORY FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def user_repo(test_db):
    """Create user repository for testing."""
    from repository import UserRepository
    
    return UserRepository(test_db)


# ═════════════════════════════════════════════════════════════════════════════
# TEST DATA FACTORIES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_user_data():
    """Return sample user data for testing."""
    return {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
    }


@pytest.fixture
def sample_users_data():
    """Return multiple sample users for testing."""
    return [
        {
            "username": f"user{i}",
            "email": f"user{i}@example.com",
            "password": "TestPassword123!",
            "full_name": f"User {i}",
        }
        for i in range(5)
    ]


@pytest.fixture
async def sample_user(user_repo, sample_user_data):
    """Create and return a sample user."""
    user = await user_repo.create(**sample_user_data)
    return user


@pytest.fixture
async def sample_users(user_repo, sample_users_data):
    """Create and return multiple sample users."""
    users = []
    for data in sample_users_data:
        user = await user_repo.create(**data)
        users.append(user)
    return users


@pytest.fixture
def valid_jwt_token(sample_user):
    """Generate valid JWT token for testing."""
    from security import JWTManager
    
    jwt_manager = JWTManager(secret_key="test-secret-key-minimum-32-characters-long")
    token = jwt_manager.create_token({"sub": str(sample_user.id)})
    return token


@pytest.fixture
def invalid_jwt_token():
    """Return invalid JWT token for testing."""
    return "invalid.jwt.token"


# ═════════════════════════════════════════════════════════════════════════════
# SECURITY FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def jwt_manager():
    """Create JWT manager for testing."""
    from security import JWTManager
    
    return JWTManager(secret_key="test-secret-key-minimum-32-characters-long")


@pytest.fixture
def rate_limiter():
    """Create rate limiter for testing."""
    from security import InMemoryRateLimiter
    
    return InMemoryRateLimiter(rpm=100)


# ═════════════════════════════════════════════════════════════════════════════
# MOCK FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_settings_dict():
    """Return settings as dictionary."""
    return {
        "ENVIRONMENT": "testing",
        "DEBUG": True,
        "JWT_SECRET_KEY": "test-secret-key-minimum-32-characters-long",
        "JWT_ENABLED": True,
        "DATABASE_ENABLED": True,
        "RATE_LIMITING_ENABLED": False,
    }


# ═════════════════════════════════════════════════════════════════════════════
# PYTEST MARKERS
# ═════════════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no I/O)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (moderate, with I/O)"
    )
    config.addinivalue_line(
        "markers", "api: API tests (requires HTTP)"
    )
    config.addinivalue_line(
        "markers", "database: Database tests"
    )
    config.addinivalue_line(
        "markers", "security: Security tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )


# ═════════════════════════════════════════════════════════════════════════════
# TEST UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def assert_helpers():
    """Provide assertion helpers."""
    class AssertHelpers:
        @staticmethod
        def is_valid_uuid(value):
            """Check if value is valid UUID."""
            import uuid
            try:
                uuid.UUID(str(value))
                return True
            except ValueError:
                return False
        
        @staticmethod
        def is_valid_email(email):
            """Check if value is valid email."""
            import re
            pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            return bool(re.match(pattern, email))
        
        @staticmethod
        def is_valid_iso_datetime(value):
            """Check if value is valid ISO datetime."""
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return True
            except (ValueError, AttributeError):
                return False
    
    return AssertHelpers()


# ═════════════════════════════════════════════════════════════════════════════
# LOGGING FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def caplog_setup(caplog):
    """Configure caplog for test logging."""
    caplog.set_level("DEBUG")
    return caplog
