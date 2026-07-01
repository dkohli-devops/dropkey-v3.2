"""
database.py — DropKey v3.2 Enterprise Database Layer

FEATURES:
  [ASYNC] Full async/await support with SQLAlchemy
  [POOL] Connection pooling with configurable parameters
  [SESSION] Session management with context managers
  [HEALTH] Health check support for monitoring
  [MODELS] Base model class with common fields
  [REPO] Repository pattern for data access
  [MIGRATIONS] Alembic migration support ready
  [ERRORS] Custom exception hierarchy
  [CONFIG] Uses settings from config.py
  [SCALABLE] Prepared for future growth

DEPENDENCIES:
  pip install sqlalchemy[asyncio] psycopg[binary] alembic

USAGE:
  from database import DatabaseManager, SessionLocal
  
  # Initialize
  db_manager = DatabaseManager(settings)
  await db_manager.initialize()
  
  # Get session
  async with SessionLocal() as session:
      # Use session
      pass
  
  # Health check
  is_healthy = await db_manager.health_check()
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Any, Dict, Type, TypeVar

from sqlalchemy import Column, Integer, DateTime, String, MetaData, create_engine, event
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.future import select

from config import config, settings

# Configure logging
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═════════════════════════════════════════════════════════════════════════════


class DatabaseException(Exception):
    """Base exception for database-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails."""
    pass


class DatabaseNotInitializedError(DatabaseException):
    """Raised when attempting to use database before initialization."""
    pass


class RepositoryError(DatabaseException):
    """Raised when repository operation fails."""
    pass


class ModelValidationError(DatabaseException):
    """Raised when model validation fails."""
    pass


# ═════════════════════════════════════════════════════════════════════════════
# BASE MODEL
# ═════════════════════════════════════════════════════════════════════════════

# Single shared Base — imported from models package so all ORM models
# (User, TransferSession, TransferFile, etc.) are registered here.
# CRITICAL: Do NOT create a second declarative_base() — tables won't be created.
from models.base import Base, BaseModel  # noqa: E402  (import after logging setup)
# Import all ORM models so SQLAlchemy registers their tables in Base.metadata
import models.user          # noqa: F401
import models.transfer_models  # noqa: F401


# BaseModel is imported from models.base above — no duplicate needed.

# ═════════════════════════════════════════════════════════════════════════════
# REPOSITORY PATTERN
# ═════════════════════════════════════════════════════════════════════════════

T = TypeVar("T", bound=BaseModel)


class BaseRepository:
    """
    Base repository class providing common CRUD operations.
    
    Provides pattern for data access layer abstraction.
    Subclass for specific models.
    
    Usage:
        class UserRepository(BaseRepository):
            model = User
        
        repo = UserRepository(session)
        user = await repo.get(1)
        users = await repo.list()
    """

    model: Type[T]

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get(self, id: int) -> Optional[T]:
        """Get record by ID."""
        try:
            stmt = select(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get {self.model.__name__}(id={id}): {e}")
            raise RepositoryError(f"Failed to retrieve record: {e}")

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """List records with pagination."""
        try:
            stmt = select(self.model).offset(skip).limit(limit)

            if order_by:
                # Support ordering: "field" or "-field" for reverse
                if order_by.startswith("-"):
                    stmt = stmt.order_by(
                        getattr(self.model, order_by[1:]).desc()
                    )
                else:
                    stmt = stmt.order_by(getattr(self.model, order_by))

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to list {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to retrieve records: {e}")

    async def count(self) -> int:
        """Count total records."""
        try:
            from sqlalchemy import func

            stmt = select(func.count(self.model.id))
            result = await self.session.execute(stmt)
            return result.scalar()
        except Exception as e:
            logger.error(f"Failed to count {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to count records: {e}")

    async def create(self, **kwargs) -> T:
        """Create new record."""
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.flush()
            return instance
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to create record: {e}")

    async def update(self, id: int, **kwargs) -> Optional[T]:
        """Update record."""
        try:
            instance = await self.get(id)
            if not instance:
                return None

            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            self.session.add(instance)
            await self.session.flush()
            return instance
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update {self.model.__name__}(id={id}): {e}")
            raise RepositoryError(f"Failed to update record: {e}")

    async def delete(self, id: int) -> bool:
        """Delete record."""
        try:
            instance = await self.get(id)
            if not instance:
                return False

            await self.session.delete(instance)
            await self.session.flush()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete {self.model.__name__}(id={id}): {e}")
            raise RepositoryError(f"Failed to delete record: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# DATABASE MANAGER
# ═════════════════════════════════════════════════════════════════════════════


class DatabaseManager:
    """
    Enterprise database manager with connection pooling and health checks.
    
    Features:
    - Async/await support
    - Connection pooling
    - Session management
    - Health checks
    - Migration support
    - Error handling
    
    Usage:
        db = DatabaseManager(settings)
        await db.initialize()
        
        async with db.session_local() as session:
            # Use session
            pass
        
        is_healthy = await db.health_check()
    """

    def __init__(self, settings):
        """Initialize database manager."""
        self.settings = settings
        self._engine: Optional[AsyncEngine] = None
        self._session_local = None
        self._initialized = False
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds

    # ════════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ════════════════════════════════════════════════════════════════════════════

    async def initialize(self) -> None:
        """Initialize database connection."""
        if self._initialized:
            return

        if not settings.DATABASE_ENABLED:
            logger.info("Database disabled in configuration")
            return

        if not settings.DATABASE_URL:
            raise DatabaseException("DATABASE_URL not configured")

        try:
            await self._create_engine()
            await self._verify_connection()
            self._initialized = True

            logger.info(
                "Database initialized successfully",
                extra={
                    "database_url": str(settings.DATABASE_URL).split("@")[0] + "@***",
                    "pool_size": settings.DATABASE_POOL_SIZE,
                    "pool_recycle": settings.DATABASE_POOL_RECYCLE,
                }
            )
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise DatabaseConnectionError(f"Database initialization failed: {e}")

    async def _create_engine(self) -> None:
        """Create async engine with connection pooling."""
        # Convert PostgreSQL DSN to async version
        database_url = str(settings.DATABASE_URL)
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        # Create engine with connection pooling
        self._engine = create_async_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=10,  # Allow up to 10 overflow connections
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,  # Test connections before using
            echo=settings.DATABASE_ECHO,
            future=True,
        )

        # Create session factory
        self._session_local = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def _verify_connection(self) -> None:
        """Verify database connection."""
        try:
            async with self._engine.begin() as connection:
                await connection.execute(select(1))
            logger.info("Database connection verified")
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to verify database connection: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        if not self._initialized:
            raise DatabaseNotInitializedError(
                "Database not initialized. Call initialize() first."
            )

        return self._session_local()

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for database session."""
        session = await self.get_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            await session.close()

    async def transactional(self, func, *args, **kwargs):
        """Execute function in database transaction."""
        async with self.session_context() as session:
            return await func(session, *args, **kwargs)

    # ════════════════════════════════════════════════════════════════════════════
    # SCHEMA MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    async def create_all(self) -> None:
        """Create all tables."""
        if not self._initialized:
            raise DatabaseNotInitializedError("Database not initialized")

        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise DatabaseException(f"Failed to create tables: {e}")

    async def drop_all(self) -> None:
        """Drop all tables (development/testing only)."""
        if not self._initialized:
            raise DatabaseNotInitializedError("Database not initialized")

        if self.settings.is_production:
            raise DatabaseException("Cannot drop tables in production")

        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise DatabaseException(f"Failed to drop tables: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # MIGRATIONS
    # ════════════════════════════════════════════════════════════════════════════

    def get_migration_config(self) -> Dict[str, Any]:
        """Get Alembic migration configuration."""
        return {
            "sqlalchemy.url": str(settings.DATABASE_URL),
            "script_location": "alembic",
            "sqlalchemy.echo": settings.DATABASE_ECHO,
        }

    # ════════════════════════════════════════════════════════════════════════════
    # HEALTH CHECKS
    # ════════════════════════════════════════════════════════════════════════════

    async def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        now = time.time()

        # Rate-limit health checks
        if now - self._last_health_check < self._health_check_interval:
            return {
                "healthy": True,
                "cached": True,
                "message": "Using cached result",
            }

        if not self._initialized:
            return {
                "healthy": False,
                "message": "Database not initialized",
            }

        try:
            async with self._engine.begin() as connection:
                start = time.time()
                await connection.execute(select(1))
                latency = (time.time() - start) * 1000  # milliseconds

            self._last_health_check = now

            return {
                "healthy": True,
                "database": "postgresql",
                "latency_ms": latency,
                "pool_size": settings.DATABASE_POOL_SIZE,
            }
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return {
                "healthy": False,
                "message": f"Database check failed: {e}",
            }

    # ════════════════════════════════════════════════════════════════════════════
    # POOL MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    async def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status."""
        if not self._engine:
            return {"healthy": False, "message": "Engine not initialized"}

        pool = self._engine.pool

        return {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "checked_in": pool.checkedout(),
            "checked_out": len(pool._all_conns) - pool.checkedout(),
            "pool_overflow": 10,  # Max overflow connections
        }

    async def dispose(self) -> None:
        """Close all pool connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database pool disposed")

    # ════════════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ════════════════════════════════════════════════════════════════════════════

    async def shutdown(self) -> None:
        """Shutdown database connection."""
        if self._engine:
            await self.dispose()
            logger.info("Database shutdown complete")


# ═════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═════════════════════════════════════════════════════════════════════════════

_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get or create database manager instance."""
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseManager(settings)

    return _db_manager


# ═════════════════════════════════════════════════════════════════════════════
# SESSION FACTORY
# ═════════════════════════════════════════════════════════════════════════════


async def get_session() -> AsyncSession:
    """
    Dependency injection function for FastAPI routes.
    
    Usage:
        @app.get("/items/")
        async def read_items(session: AsyncSession = Depends(get_session)):
            # Use session
            pass
    """
    db_manager = get_db_manager()
    async with db_manager.session_context() as session:
        yield session


# Alias for convenience
SessionLocal = get_session


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE MODELS (Uncomment and customize for your use case)
# ═════════════════════════════════════════════════════════════════════════════

"""
Example model definitions:

from sqlalchemy import Column, String, Boolean, Integer

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    async def verify_password(self, password: str) -> bool:
        # Custom business logic
        pass


class TransferSession(BaseModel):
    __tablename__ = "transfer_sessions"
    
    key = Column(String(32), unique=True, nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    
    async def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


# Repository examples:

class UserRepository(BaseRepository):
    model = User
    
    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(self.model).where(self.model.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class TransferSessionRepository(BaseRepository):
    model = TransferSession
    
    async def get_active(self, owner_id: int) -> List[TransferSession]:
        stmt = select(self.model).where(
            (self.model.owner_id == owner_id) &
            (self.model.is_completed == False) &
            (self.model.expires_at > datetime.utcnow())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
"""


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═════════════════════════════════════════════════════════════════════════════

"""
Usage examples:

# 1. Initialize in main.py:

from database import get_db_manager

@app.on_event("startup")
async def startup():
    db_manager = get_db_manager()
    await db_manager.initialize()


# 2. Use in routes:

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

@app.get("/users/")
async def list_users(session: AsyncSession = Depends(get_session)):
    stmt = select(User)
    result = await session.execute(stmt)
    return result.scalars().all()


# 3. Use repositories:

from database import get_session, BaseRepository

@app.get("/users/{user_id}")
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.get(user_id)
    return user


# 4. Health check in health endpoints:

from database import get_db_manager

@app.get("/health/db")
async def db_health():
    db_manager = get_db_manager()
    health = await db_manager.health_check()
    
    if not health["healthy"]:
        raise HTTPException(status_code=503)
    
    return health


# 5. Create tables (development only):

from database import get_db_manager

@app.on_event("startup")
async def setup_database():
    db_manager = get_db_manager()
    await db_manager.initialize()
    
    if settings.is_development:
        await db_manager.create_all()


# 6. Transactional operations:

from database import get_db_manager

async def transfer_funds(from_id: int, to_id: int, amount: float):
    db_manager = get_db_manager()
    
    async def do_transfer(session):
        # All operations committed together or rolled back
        sender = await UserRepository(session).get(from_id)
        receiver = await UserRepository(session).get(to_id)
        
        sender.balance -= amount
        receiver.balance += amount
        
        session.add(sender)
        session.add(receiver)
    
    await db_manager.transactional(do_transfer)
"""


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test database connection."""
        db_manager = get_db_manager()

        try:
            await db_manager.initialize()
            print("✅ Database initialized")

            # Health check
            health = await db_manager.health_check()
            print(f"✅ Health check: {health}")

            # Pool status
            pool_status = await db_manager.get_pool_status()
            print(f"✅ Pool status: {pool_status}")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await db_manager.shutdown()

    asyncio.run(test())
