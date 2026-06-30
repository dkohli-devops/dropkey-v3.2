# ═════════════════════════════════════════════════════════════════════════════
# health.py — Health Check Endpoints for DropKey v3.2
#
# Endpoints:
#   • /health — Full health status
#   • /health/live — Liveness probe (is container running?)
#   • /health/ready — Readiness probe (can container handle traffic?)
#   • /health/startup — Startup probe (has container finished starting?)
# ═════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


# ═════════════════════════════════════════════════════════════════════════════
# Models
# ═════════════════════════════════════════════════════════════════════════════


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    status: HealthStatus
    timestamp: datetime
    message: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Complete health status response."""
    status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, ComponentHealth]
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness probe response."""
    status: HealthStatus
    timestamp: datetime
    ready: bool
    checks: Dict[str, bool]


# ═════════════════════════════════════════════════════════════════════════════
# Health Check Service
# ═════════════════════════════════════════════════════════════════════════════


class HealthService:
    """Service for health checks."""

    def __init__(self):
        """Initialize health service."""
        self.start_time = datetime.utcnow()
        self.components_status: Dict[str, ComponentHealth] = {}

    async def check_database(
        self,
        db: Optional[AsyncSession] = None,
    ) -> ComponentHealth:
        """Check database connectivity."""
        start_time = datetime.utcnow()
        
        try:
            if db is None:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    timestamp=start_time,
                    message="No database session available",
                )

            # Execute simple query
            await db.execute(sa.text("SELECT 1"))
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                message="Database connection successful",
                latency_ms=latency_ms,
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                message=f"Database error: {str(e)}",
            )

    async def check_redis(
        self,
        redis_client: Optional[Any] = None,
    ) -> ComponentHealth:
        """Check Redis connectivity."""
        start_time = datetime.utcnow()
        
        try:
            if redis_client is None:
                return ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    timestamp=start_time,
                    message="Redis not configured (optional)",
                )

            # Ping Redis
            await redis_client.ping()
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                message="Redis connection successful",
                latency_ms=latency_ms,
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                timestamp=datetime.utcnow(),
                message=f"Redis error: {str(e)} (cache unavailable)",
            )

    async def check_memory(
        self,
        max_memory_mb: int = 1000,
    ) -> ComponentHealth:
        """Check memory usage."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            status = HealthStatus.HEALTHY
            if memory_mb > max_memory_mb * 0.9:
                status = HealthStatus.DEGRADED
            elif memory_mb > max_memory_mb:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                status=status,
                timestamp=datetime.utcnow(),
                message=f"Memory usage: {memory_mb:.2f}MB / {max_memory_mb}MB",
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                message=f"Could not check memory: {str(e)}",
            )

    async def check_disk(
        self,
        path: str = "/",
        min_free_gb: float = 1.0,
    ) -> ComponentHealth:
        """Check disk space."""
        try:
            import shutil
            stats = shutil.disk_usage(path)
            free_gb = stats.free / (1024 ** 3)
            
            status = HealthStatus.HEALTHY
            if free_gb < min_free_gb * 2:
                status = HealthStatus.DEGRADED
            elif free_gb < min_free_gb:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                status=status,
                timestamp=datetime.utcnow(),
                message=f"Disk free: {free_gb:.2f}GB",
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                message=f"Could not check disk: {str(e)}",
            )

    async def check_all(
        self,
        db: Optional[AsyncSession] = None,
        redis_client: Optional[Any] = None,
    ) -> HealthResponse:
        """Check all components."""
        checks = {
            "database": await self.check_database(db),
            "redis": await self.check_redis(redis_client),
            "memory": await self.check_memory(),
            "disk": await self.check_disk(),
        }

        # Determine overall status
        statuses = [check.status for check in checks.values()]
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            uptime_seconds=uptime,
            components=checks,
            version="3.2.0",
            environment="production",
        )

    async def check_ready(
        self,
        db: Optional[AsyncSession] = None,
        redis_client: Optional[Any] = None,
    ) -> ReadinessResponse:
        """Check if service is ready to accept traffic."""
        start_time = datetime.utcnow()
        
        db_check = await self.check_database(db)
        redis_check = await self.check_redis(redis_client)
        
        checks = {
            "database": db_check.status == HealthStatus.HEALTHY,
            "redis": redis_check.status != HealthStatus.UNHEALTHY,
            "memory": (await self.check_memory()).status != HealthStatus.UNHEALTHY,
            "disk": (await self.check_disk()).status != HealthStatus.UNHEALTHY,
        }

        ready = all(checks.values())
        status = HealthStatus.HEALTHY if ready else HealthStatus.UNHEALTHY

        return ReadinessResponse(
            status=status,
            timestamp=datetime.utcnow(),
            ready=ready,
            checks=checks,
        )

    async def check_live(self) -> ComponentHealth:
        """Check if container is alive."""
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            timestamp=datetime.utcnow(),
            message="Container is running",
        )


# ═════════════════════════════════════════════════════════════════════════════
# Router
# ═════════════════════════════════════════════════════════════════════════════


def create_health_router(health_service: HealthService) -> APIRouter:
    """Create health check router."""
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get(
        "/",
        response_model=HealthResponse,
        summary="Full health status",
        description="Returns complete health status including all components",
    )
    async def health(
        db: Optional[AsyncSession] = Depends(None),  # Inject your DB session
    ) -> HealthResponse:
        """Get full health status."""
        return await health_service.check_all(db=db)

    @router.get(
        "/live",
        response_model=ComponentHealth,
        summary="Liveness probe",
        description="Check if container is alive (Kubernetes liveness probe)",
    )
    async def health_live() -> ComponentHealth:
        """Liveness probe - is container running?"""
        return await health_service.check_live()

    @router.get(
        "/ready",
        response_model=ReadinessResponse,
        summary="Readiness probe",
        description="Check if service is ready to accept traffic (Kubernetes readiness probe)",
    )
    async def health_ready(
        db: Optional[AsyncSession] = Depends(None),  # Inject your DB session
    ) -> ReadinessResponse:
        """Readiness probe - can container handle traffic?"""
        response = await health_service.check_ready(db=db)
        if response.status == HealthStatus.UNHEALTHY:
            raise HTTPException(
                status_code=503,
                detail="Service not ready",
            )
        return response

    @router.get(
        "/startup",
        response_model=ComponentHealth,
        summary="Startup probe",
        description="Check if container has finished starting (Kubernetes startup probe)",
    )
    async def health_startup(
        db: Optional[AsyncSession] = Depends(None),  # Inject your DB session
    ) -> ComponentHealth:
        """Startup probe - has container finished starting?"""
        ready_response = await health_service.check_ready(db=db)
        if ready_response.status == HealthStatus.UNHEALTHY:
            raise HTTPException(
                status_code=503,
                detail="Service still starting",
            )
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            timestamp=datetime.utcnow(),
            message="Service startup complete",
        )

    return router


# ═════════════════════════════════════════════════════════════════════════════
# Integration with FastAPI
# ═════════════════════════════════════════════════════════════════════════════

# Example usage in main.py:
#
# from fastapi import FastAPI
# from health import HealthService, create_health_router
#
# app = FastAPI()
# health_service = HealthService()
# 
# health_router = create_health_router(health_service)
# app.include_router(health_router)
#
# # Kubernetes will use these endpoints:
# # Liveness:  GET /health/live
# # Readiness: GET /health/ready
# # Startup:   GET /health/startup
