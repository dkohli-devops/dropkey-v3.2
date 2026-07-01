# ═══════════════════════════════════════════════════════
# logger.py — Centralized Logger for DropKey v3.2
# Used by: security.py, session_manager.py, api_routes.py
# ═══════════════════════════════════════════════════════

import functools
import time
import logging
from typing import Callable, Any

try:
    from logging_config import StructuredLogger
    _use_structured = True
except ImportError:
    _use_structured = False

def _make_logger(name: str):
    if _use_structured:
        return StructuredLogger(name)
    return logging.getLogger(name)

# ── Module-level logger instances (imported by other modules) ──
app_logger      = _make_logger("dropkey.app")
security_logger = _make_logger("dropkey.security")
transfer_logger = _make_logger("dropkey.transfer")
db_logger       = _make_logger("dropkey.database")


def audit_log(event: str, **kwargs: Any) -> None:
    """
    Write a security audit log entry.
    Used by: security.py, session_manager.py
    """
    if _use_structured:
        security_logger.info(f"AUDIT:{event}", **kwargs)
    else:
        security_logger.info("AUDIT:%s | %s", event, kwargs)


def log_duration(func: Callable) -> Callable:
    """
    Decorator — logs how long an async endpoint takes.
    Used by: api_routes.py
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            if _use_structured:
                app_logger.info(
                    f"{func.__name__} completed",
                    duration_ms=round(duration_ms, 2),
                )
            else:
                app_logger.info("%s completed in %.2fms", func.__name__, duration_ms)
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            if _use_structured:
                app_logger.error(
                    f"{func.__name__} failed",
                    duration_ms=round(duration_ms, 2),
                    error=str(exc),
                )
            else:
                app_logger.error("%s failed after %.2fms: %s", func.__name__, duration_ms, exc)
            raise
    return wrapper
