# ═════════════════════════════════════════════════════════════════════════════
# metrics.py — Prometheus Metrics Configuration for DropKey v3.2
#
# Metrics:
#   • HTTP request metrics
#   • Database query metrics
#   • Business logic metrics
#   • System metrics
# ═════════════════════════════════════════════════════════════════════════════

from typing import Callable, Optional
import time
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import psutil


# ═════════════════════════════════════════════════════════════════════════════
# HTTP Metrics
# ═════════════════════════════════════════════════════════════════════════════

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_request_size_bytes = Summary(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
)

http_response_size_bytes = Summary(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint', 'status'],
)

# ═════════════════════════════════════════════════════════════════════════════
# Database Metrics
# ═════════════════════════════════════════════════════════════════════════════

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table', 'status'],
)

db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections',
)

db_pool_size = Gauge(
    'db_pool_size',
    'Database connection pool size',
)

# ═════════════════════════════════════════════════════════════════════════════
# Business Logic Metrics
# ═════════════════════════════════════════════════════════════════════════════

users_total = Counter(
    'users_total',
    'Total users',
    ['status'],
)

transfers_total = Counter(
    'transfers_total',
    'Total file transfers',
    ['status'],
)

transfers_bytes_total = Counter(
    'transfers_bytes_total',
    'Total bytes transferred',
    ['direction'],  # upload, download
)

transfer_duration_seconds = Histogram(
    'transfer_duration_seconds',
    'Transfer duration in seconds',
    ['type'],  # upload, download
)

active_connections = Gauge(
    'active_connections',
    'Active WebSocket connections',
)

# ═════════════════════════════════════════════════════════════════════════════
# Authentication Metrics
# ═════════════════════════════════════════════════════════════════════════════

auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['method', 'status'],  # method: password, jwt, oauth
)

auth_failures_total = Counter(
    'auth_failures_total',
    'Total authentication failures',
    ['reason'],  # invalid_credentials, expired_token, etc
)

# ═════════════════════════════════════════════════════════════════════════════
# System Metrics
# ═════════════════════════════════════════════════════════════════════════════

app_info = Counter(
    'app_info',
    'Application info',
    ['version', 'environment'],
)

process_cpu_percent = Gauge(
    'process_cpu_percent',
    'Process CPU usage percentage',
)

process_memory_bytes = Gauge(
    'process_memory_bytes',
    'Process memory usage in bytes',
)

process_virtual_memory_bytes = Gauge(
    'process_virtual_memory_bytes',
    'Process virtual memory usage in bytes',
)

# ═════════════════════════════════════════════════════════════════════════════
# Error Metrics
# ═════════════════════════════════════════════════════════════════════════════

exceptions_total = Counter(
    'exceptions_total',
    'Total exceptions',
    ['type', 'endpoint'],
)

errors_total = Counter(
    'errors_total',
    'Total errors by status code',
    ['status_code'],
)

# ═════════════════════════════════════════════════════════════════════════════
# Cache Metrics
# ═════════════════════════════════════════════════════════════════════════════

cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['key_type'],
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['key_type'],
)

cache_operations_duration_seconds = Histogram(
    'cache_operations_duration_seconds',
    'Cache operation duration in seconds',
    ['operation'],  # get, set, delete
)

# ═════════════════════════════════════════════════════════════════════════════
# Middleware for automatic HTTP metrics
# ═════════════════════════════════════════════════════════════════════════════


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and collect metrics."""
        method = request.method
        endpoint = request.url.path

        start_time = time.time()
        
        # Estimate request size
        request_size = len(await request.body()) if request.method in ['POST', 'PUT'] else 0
        http_request_size_bytes.labels(method=method, endpoint=endpoint).observe(request_size)

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            exceptions_total.labels(type=type(exc).__name__, endpoint=endpoint).inc()
            errors_total.labels(status_code=500).inc()
            raise

        # Record metrics
        duration = time.time() - start_time
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)
        
        http_response_size_bytes.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).observe(len(response.body) if hasattr(response, 'body') else 0)

        if status >= 400:
            errors_total.labels(status_code=status).inc()

        return response


# ═════════════════════════════════════════════════════════════════════════════
# Context managers for manual metric collection
# ═════════════════════════════════════════════════════════════════════════════


@contextmanager
def track_db_query(operation: str, table: str):
    """Context manager to track database queries."""
    start_time = time.time()
    try:
        yield
        db_queries_total.labels(
            operation=operation,
            table=table,
            status='success',
        ).inc()
    except Exception as e:
        db_queries_total.labels(
            operation=operation,
            table=table,
            status='error',
        ).inc()
        raise
    finally:
        duration = time.time() - start_time
        db_query_duration_seconds.labels(
            operation=operation,
            table=table,
        ).observe(duration)


@contextmanager
def track_transfer(transfer_type: str):
    """Context manager to track file transfers."""
    start_time = time.time()
    try:
        yield
        transfers_total.labels(status='success').inc()
    except Exception as e:
        transfers_total.labels(status='error').inc()
        raise
    finally:
        duration = time.time() - start_time
        transfer_duration_seconds.labels(type=transfer_type).observe(duration)


@contextmanager
def track_cache_operation(operation: str):
    """Context manager to track cache operations."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        cache_operations_duration_seconds.labels(
            operation=operation,
        ).observe(duration)


# ═════════════════════════════════════════════════════════════════════════════
# System metrics collection
# ═════════════════════════════════════════════════════════════════════════════


def update_system_metrics() -> None:
    """Update system metrics."""
    try:
        process = psutil.Process()
        
        # CPU and memory metrics
        process_cpu_percent.set(process.cpu_percent(interval=0.1))
        process_memory_bytes.set(process.memory_info().rss)
        process_virtual_memory_bytes.set(process.memory_info().vms)
    except Exception:
        pass  # Silently fail if metrics unavailable


# ═════════════════════════════════════════════════════════════════════════════
# Integration with FastAPI
# ═════════════════════════════════════════════════════════════════════════════

# Example usage in main.py:
#
# from fastapi import FastAPI
# from fastapi.responses import Response
# from prometheus_client import generate_latest
# from metrics import MetricsMiddleware
#
# app = FastAPI()
# app.add_middleware(MetricsMiddleware)
#
# @app.get('/metrics')
# async def metrics():
#     """Prometheus metrics endpoint."""
#     return Response(
#         generate_latest(),
#         media_type='text/plain; charset=utf-8'
#     )
#
# @app.on_event('startup')
# async def startup():
#     """Initialize metrics on startup."""
#     app_info.labels(version='3.2.0', environment='production').inc()
