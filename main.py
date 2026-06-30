# ═════════════════════════════════════════════════════════════════════════════
# main.py — DropKey v3.2 Application Entry Point
#
# Integrates all modules into a production-ready FastAPI application
# Layer: Application (Orchestration)
# ═════════════════════════════════════════════════════════════════════════════

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest
from fastapi.responses import Response

# Configuration & Setup
from config import Config
from logging_config import setup_logging, StructuredLogger
from settings import Settings

# Database & Cache
from database import init_db, get_db, Database
from cache import CacheManager

# Security & Sessions
from security import verify_token
from session_manager import SessionManager

# Middleware & Monitoring
from metrics import MetricsMiddleware, app_info
from health import HealthService, create_health_router

# API Routes
from api_routes import router as api_router

# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION SETUP
# ═════════════════════════════════════════════════════════════════════════════

# Setup logging
setup_logging(log_level=Config.LOG_LEVEL)
logger = StructuredLogger(__name__)

# Global instances (initialized during startup)
db: Optional[Database] = None
cache: Optional[CacheManager] = None
session_manager: Optional[SessionManager] = None
health_service: Optional[HealthService] = None

# ═════════════════════════════════════════════════════════════════════════════
# LIFESPAN CONTEXT (Startup/Shutdown)
# ═════════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: startup and shutdown.
    
    Startup:
        - Initialize database connection
        - Initialize cache connection
        - Initialize session manager
        - Initialize health service
        - Record app initialization
    
    Shutdown:
        - Close database connection
        - Close cache connection
        - Clear sessions
        - Log shutdown
    """
    global db, cache, session_manager, health_service
    
    # ─────────────────────────────────────────────────────────────────────────
    # STARTUP
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(
        "Application startup initiated",
        version=Config.VERSION,
        environment=Config.ENVIRONMENT,
        debug=Config.DEBUG,
    )

    try:
        # Initialize database
        if Config.DATABASE_ENABLED:
            logger.info("Initializing database connection...")
            db = Database(
                url=Config.DATABASE_URL,
                echo=Config.DEBUG,
                pool_size=Config.DATABASE_POOL_SIZE,
                max_overflow=Config.DATABASE_MAX_OVERFLOW,
            )
            await init_db(db)
            logger.info("✓ Database initialized successfully")
        
        # Initialize cache
        if Config.REDIS_ENABLED:
            logger.info("Initializing cache connection...")
            cache = CacheManager(
                redis_url=Config.REDIS_URL,
                default_ttl=Config.REDIS_DEFAULT_TTL,
                max_connections=Config.REDIS_MAX_CONNECTIONS,
            )
            await cache.connect()
            logger.info("✓ Cache initialized successfully")
        
        # Initialize session manager
        logger.info("Initializing session manager...")
        session_manager = SessionManager(
            session_timeout=Config.SESSION_TIMEOUT,
            max_sessions_per_user=Config.MAX_SESSIONS_PER_USER,
            cache=cache if Config.REDIS_ENABLED else None,
        )
        logger.info("✓ Session manager initialized")
        
        # Initialize health service
        logger.info("Initializing health service...")
        health_service = HealthService()
        logger.info("✓ Health service initialized")
        
        # Record app startup in metrics
        app_info.labels(
            version=Config.VERSION,
            environment=Config.ENVIRONMENT,
        ).inc()
        
        logger.info(
            "✓ Application startup complete",
            version=Config.VERSION,
            environment=Config.ENVIRONMENT,
        )

    except Exception as e:
        logger.error(
            "Critical error during startup",
            error=str(e),
            exc_info=True,
        )
        raise

    # ─────────────────────────────────────────────────────────────────────────
    # YIELD (Application running)
    # ─────────────────────────────────────────────────────────────────────────
    yield

    # ─────────────────────────────────────────────────────────────────────────
    # SHUTDOWN
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("Application shutdown initiated")

    try:
        # Close database connection
        if db is not None:
            logger.info("Closing database connection...")
            await db.close()
            logger.info("✓ Database connection closed")
        
        # Close cache connection
        if cache is not None:
            logger.info("Closing cache connection...")
            await cache.disconnect()
            logger.info("✓ Cache connection closed")
        
        # Clear sessions
        if session_manager is not None:
            logger.info("Clearing sessions...")
            session_manager.clear_all()
            logger.info("✓ Sessions cleared")
        
        logger.info("✓ Application shutdown complete")

    except Exception as e:
        logger.error(
            "Error during shutdown",
            error=str(e),
            exc_info=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION FACTORY
# ═════════════════════════════════════════════════════════════════════════════


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Setup:
        - Create FastAPI instance
        - Configure middleware
        - Register routes
        - Configure error handlers
        - Add health checks
        - Add metrics endpoints
    
    Returns:
        Configured FastAPI application ready for deployment
    """
    
    # Create FastAPI app
    app = FastAPI(
        title="DropKey",
        description="Enterprise P2P encrypted file transfer",
        version=Config.VERSION,
        docs_url="/docs" if not Config.PRODUCTION else None,
        redoc_url="/redoc" if not Config.PRODUCTION else None,
        openapi_url="/openapi.json" if not Config.PRODUCTION else None,
        lifespan=lifespan,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MIDDLEWARE SETUP
    # ─────────────────────────────────────────────────────────────────────────

    # Metrics middleware (FIRST - capture all requests)
    app.add_middleware(MetricsMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=3600,
    )

    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=Config.ALLOWED_HOSTS,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # ROUTES
    # ─────────────────────────────────────────────────────────────────────────

    # Include API routes
    app.include_router(api_router, prefix="/api", tags=["api"])

    # Include health check routes
    health_router = create_health_router(health_service)
    app.include_router(health_router, tags=["health"])

    # ─────────────────────────────────────────────────────────────────────────
    # METRICS ENDPOINT
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/metrics", tags=["monitoring"])
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            generate_latest(),
            media_type="text/plain; charset=utf-8",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ERROR HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        logger.warning(
            "HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error(
            "Unhandled exception",
            error=str(exc),
            path=request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # REQUEST/RESPONSE LOGGING
    # ─────────────────────────────────────────────────────────────────────────

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log HTTP requests."""
        import time
        
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        logger.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # ROOT ENDPOINT
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/", tags=["info"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "DropKey",
            "version": Config.VERSION,
            "environment": Config.ENVIRONMENT,
            "docs": "/docs" if not Config.PRODUCTION else None,
            "health": "/health",
            "metrics": "/metrics",
        }

    return app


# ═════════════════════════════════════════════════════════════════════════════
# DEPENDENCY INJECTION
# ═════════════════════════════════════════════════════════════════════════════


async def get_database():
    """Dependency for database access."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


async def get_cache():
    """Dependency for cache access."""
    if cache is None:
        raise HTTPException(status_code=503, detail="Cache not available")
    return cache


async def get_session_mgr():
    """Dependency for session manager access."""
    if session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not available")
    return session_manager


async def get_health_service():
    """Dependency for health service access."""
    if health_service is None:
        raise HTTPException(status_code=503, detail="Health service not available")
    return health_service


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION INSTANCE
# ═════════════════════════════════════════════════════════════════════════════

app = create_app()


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "Starting application server",
        host=Config.HOST,
        port=Config.PORT,
        workers=Config.WORKERS,
    )
    
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        workers=Config.WORKERS if not Config.DEBUG else 1,
        reload=Config.DEBUG,
        log_level=Config.LOG_LEVEL.lower(),
        access_log=not Config.PRODUCTION,
    )
