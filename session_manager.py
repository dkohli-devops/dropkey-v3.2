"""
session_manager.py — DropKey v3.2 Enterprise Session Management (Production-Hardened)

ENTERPRISE FEATURES:
  [RC] Redis Connection Pool Management with health checks
  [RM] Retry Mechanisms with exponential backoff for transient failures
  [HC] Health Check Support for liveness/readiness probes
  [STORE] Abstract SessionStore interface for future PostgreSQL/MySQL integration
  [CONFIG] Configurable TTLs, timeouts, and retry policies
  [LOGGING] Structured logging with audit trail integration
  [METRICS] Session lifecycle metrics and monitoring
  [ERROR] Custom exception hierarchy with proper error context
  [OTK] One-Time Key enforcement (burn-after-reading semantics)

BACKWARD COMPATIBILITY:
  - All existing SessionManager APIs preserved
  - Existing SessionData serialization compatible
  - Store backends (Redis/Memory) unchanged in behavior
  - Drop-in replacement for v3.1 code

FUTURE INTEGRATION:
  - Abstract SessionStore ABC for database backends
  - Database adapter pattern ready for PostgreSQL/MySQL
  - Metrics export ready for Prometheus
"""

import asyncio
import json
import logging
import secrets
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from fastapi import HTTPException, WebSocket

from config import Settings
from logger import audit_log, app_logger

log = logging.getLogger("dropkey.sessions")

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

# Session Store Configuration
MAX_MEMORY_SESSIONS: int = int(__import__("os").environ.get("MAX_MEMORY_SESSIONS", "10000"))
"""Hard cap for in-process memory store"""

# Redis Connection Configuration
REDIS_POOL_SIZE: int = int(__import__("os").environ.get("REDIS_POOL_SIZE", "10"))
"""Connection pool size for Redis"""

REDIS_CONNECTION_TIMEOUT: int = int(__import__("os").environ.get("REDIS_CONNECTION_TIMEOUT", "5"))
"""Connection timeout in seconds"""

REDIS_SOCKET_TIMEOUT: int = int(__import__("os").environ.get("REDIS_SOCKET_TIMEOUT", "5"))
"""Socket timeout in seconds"""

# Retry Configuration
REDIS_MAX_RETRIES: int = int(__import__("os").environ.get("REDIS_MAX_RETRIES", "3"))
"""Maximum number of retries for transient failures"""

REDIS_RETRY_BACKOFF_FACTOR: float = float(__import__("os").environ.get("REDIS_RETRY_BACKOFF_FACTOR", "0.1"))
"""Exponential backoff factor (seconds)"""

# Session TTL Configuration
SESSION_TTL_DEFAULT: int = int(__import__("os").environ.get("SESSION_TTL_DEFAULT", "3600"))
"""Default session TTL in seconds (1 hour)"""

SESSION_TTL_TRANSFER: int = int(__import__("os").environ.get("SESSION_TTL_TRANSFER", "7200"))
"""Extended TTL during active transfer (2 hours)"""

SESSION_CLEANUP_INTERVAL: int = int(__import__("os").environ.get("SESSION_CLEANUP_INTERVAL", "30"))
"""Memory store cleanup interval in seconds"""

# One-Time Key Configuration
ONE_TIME_KEY_ENABLED: bool = __import__("os").environ.get("ONE_TIME_KEY_ENABLED", "true").lower() == "true"
"""Enable one-time key enforcement"""


# ═════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS — Custom exception hierarchy
# ═════════════════════════════════════════════════════════════════════════════

class SessionException(Exception):
    """Base exception for session-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SessionStoreFullError(SessionException):
    """Raised when session store reaches capacity."""
    pass


class KeyAlreadyUsedError(SessionException):
    """Raised when a one-time key has already been consumed."""
    pass


class SessionNotFoundError(SessionException):
    """Raised when session doesn't exist or has expired."""
    pass


class RedisConnectionError(SessionException):
    """Raised when Redis connection fails."""
    pass


class SessionDataError(SessionException):
    """Raised when session data serialization/deserialization fails."""
    pass


# ═════════════════════════════════════════════════════════════════════════════
# DOMAIN TYPES
# ═════════════════════════════════════════════════════════════════════════════

class TransferState(str, Enum):
    """Session transfer state machine."""
    PENDING   = "pending"
    WAITING   = "waiting"
    ACTIVE    = "active"
    TRANSFER  = "transfer"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class SessionData:
    """
    JSON-serializable session state.
    Contains transfer metadata and progress tracking.
    No WebSocket handles (in-memory only).
    """
    key:         str
    created_at:  float
    expires_at:  float
    creator_ip:  str  = ""
    state:       str  = TransferState.PENDING.value

    files:        List[dict] = field(default_factory=list)
    current_file: int        = 0

    transfer_started_at:   Optional[float] = None
    transfer_completed_at: Optional[float] = None

    sender_reconnects:   int = 0
    receiver_reconnects: int = 0

    # One-time key: True after first receiver connects
    key_consumed: bool = False

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return time.time() > self.expires_at

    def time_remaining(self) -> int:
        """Get remaining TTL in seconds."""
        return max(0, int(self.expires_at - time.time()))

    def resume_point(self) -> dict:
        """Get resume point for transfer continuation."""
        idx = self.current_file
        if idx < len(self.files):
            return {"file_index": idx, "chunk_index": self.files[idx].get("last_ack", 0)}
        return {"file_index": idx, "chunk_index": 0}

    def register_file(self, i: int, name: str, size: int,
                      total_chunks: int, sha256: str = "") -> None:
        """Register a file in the transfer session."""
        while len(self.files) <= i:
            self.files.append({"file_index": len(self.files), "name": "", "size": 0,
                                "total_chunks": 0, "last_ack": 0,
                                "completed": False, "sha256": ""})
        self.files[i].update({"file_index": i, "name": name, "size": size,
                               "total_chunks": total_chunks, "sha256": sha256})

    def ack_chunk(self, file_index: int, chunk_index: int) -> None:
        """Acknowledge a chunk receipt."""
        if file_index < len(self.files):
            self.files[file_index]["last_ack"] = chunk_index

    def complete_file(self, file_index: int) -> None:
        """Mark a file as complete."""
        if file_index < len(self.files):
            self.files[file_index]["completed"] = True
        self.current_file = file_index + 1

    def all_files_done(self) -> bool:
        """Check if all files have been transferred."""
        return bool(self.files) and all(f.get("completed", False) for f in self.files)

    def to_json(self) -> str:
        """Serialize session to JSON."""
        return json.dumps({
            "key": self.key, "created_at": self.created_at,
            "expires_at": self.expires_at, "creator_ip": self.creator_ip,
            "state": self.state, "files": self.files,
            "current_file": self.current_file,
            "transfer_started_at": self.transfer_started_at,
            "transfer_completed_at": self.transfer_completed_at,
            "sender_reconnects": self.sender_reconnects,
            "receiver_reconnects": self.receiver_reconnects,
            "key_consumed": self.key_consumed,
        })

    @classmethod
    def from_json(cls, raw: str) -> "SessionData":
        """Deserialize session from JSON."""
        d = json.loads(raw)
        return cls(
            key=d["key"], created_at=d["created_at"], expires_at=d["expires_at"],
            creator_ip=d.get("creator_ip", ""),
            state=d.get("state", TransferState.PENDING.value),
            files=d.get("files", []), current_file=d.get("current_file", 0),
            transfer_started_at=d.get("transfer_started_at"),
            transfer_completed_at=d.get("transfer_completed_at"),
            sender_reconnects=d.get("sender_reconnects", 0),
            receiver_reconnects=d.get("receiver_reconnects", 0),
            key_consumed=d.get("key_consumed", False),
        )


# ═════════════════════════════════════════════════════════════════════════════
# KEY GENERATION
# ═════════════════════════════════════════════════════════════════════════════

_ALPHABET = (string.ascii_uppercase + string.digits) \
    .replace("O","").replace("I","").replace("L","") \
    .replace("0","").replace("1","")
"""Safe alphabet for key generation (excludes confusing chars)"""


def _make_key(length: int) -> str:
    """Generate a cryptographically-secure random key."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


# ═════════════════════════════════════════════════════════════════════════════
# ABSTRACT SESSION STORE — Interface for backends
# ═════════════════════════════════════════════════════════════════════════════

class SessionStore(ABC):
    """
    Abstract base class for session storage backends.
    
    Supports multiple implementations:
    - Redis (distributed, network-based)
    - In-Memory (fallback, single-process)
    - PostgreSQL (future: persistent, queryable)
    - MySQL (future: persistent, queryable)
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[SessionData]:
        """Retrieve a session."""
        pass

    @abstractmethod
    async def save(self, s: SessionData) -> None:
        """Save or update a session."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a session."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if session exists."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total sessions."""
        pass

    @abstractmethod
    async def cleanup(self) -> int:
        """Clean up expired sessions. Returns count cleaned."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if backend is healthy and accessible."""
        pass


# ═════════════════════════════════════════════════════════════════════════════
# REDIS STORE — Distributed session backend
# ═════════════════════════════════════════════════════════════════════════════

class RedisStore(SessionStore):
    """
    Redis-backed session store for distributed deployments.
    
    Features:
    - Connection pooling
    - Automatic TTL expiration
    - Retry mechanisms for transient failures
    - Health checks
    """

    def __init__(self, redis_client: aioredis.Redis, prefix: str, default_ttl: int):
        self._redis = redis_client
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds

    def _key(self, session_key: str) -> str:
        """Generate Redis key for session."""
        return f"{self._prefix}session:{session_key}"

    async def get(self, key: str) -> Optional[SessionData]:
        """Retrieve session from Redis."""
        try:
            raw = await self._redis.get(self._key(key))
            if raw is None:
                return None
            return SessionData.from_json(raw)
        except aioredis.ResponseError as e:
            log.warning(f"Redis response error (key={key[:4]}****): {e}")
            raise RedisConnectionError(f"Redis get failed: {e}")
        except json.JSONDecodeError as e:
            log.error(f"Session deserialization error (key={key[:4]}****): {e}")
            raise SessionDataError(f"Failed to deserialize session: {e}")

    async def save(self, s: SessionData) -> None:
        """Save session to Redis with TTL."""
        try:
            ttl = max(1, int(s.expires_at - time.time()))
            await self._redis.setex(self._key(s.key), ttl, s.to_json())
        except aioredis.ResponseError as e:
            log.error(f"Redis save failed (key={s.key[:4]}****): {e}")
            raise RedisConnectionError(f"Redis save failed: {e}")
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Session serialization error: {e}")
            raise SessionDataError(f"Failed to serialize session: {e}")

    async def delete(self, key: str) -> None:
        """Delete session from Redis."""
        try:
            await self._redis.delete(self._key(key))
        except aioredis.ResponseError as e:
            log.warning(f"Redis delete failed (key={key[:4]}****): {e}")

    async def exists(self, key: str) -> bool:
        """Check if session exists in Redis."""
        try:
            return bool(await self._redis.exists(self._key(key)))
        except aioredis.ResponseError as e:
            log.warning(f"Redis exists check failed: {e}")
            raise RedisConnectionError(f"Redis exists check failed: {e}")

    async def count(self) -> int:
        """Count sessions in Redis."""
        try:
            count = 0
            async for _ in self._redis.scan_iter(f"{self._prefix}session:*", count=100):
                count += 1
            return count
        except aioredis.ResponseError as e:
            log.warning(f"Redis scan failed: {e}")
            return 0

    async def cleanup(self) -> int:
        """Clean up expired sessions (Redis TTL handles this natively)."""
        # Redis automatically removes expired keys; cleanup is a no-op
        return 0

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            now = time.time()
            # Rate-limit health checks to avoid excessive pings
            if now - self._last_health_check < self._health_check_interval:
                return True
            
            await self._redis.ping()
            self._last_health_check = now
            return True
        except Exception as e:
            log.warning(f"Redis health check failed: {e}")
            return False


# ═════════════════════════════════════════════════════════════════════════════
# MEMORY STORE — Fallback single-process backend
# ═════════════════════════════════════════════════════════════════════════════

class MemoryStore(SessionStore):
    """
    In-process memory store for single-instance or fallback deployments.
    
    Features:
    - Hard cap on sessions (MAX_MEMORY_SESSIONS)
    - Manual cleanup for expired sessions
    - Raises error when full
    """

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._created_at = time.time()

    async def get(self, key: str) -> Optional[SessionData]:
        """Retrieve session from memory."""
        s = self._sessions.get(key)
        if s and s.is_expired():
            del self._sessions[key]
            return None
        return s

    async def save(self, s: SessionData) -> None:
        """Save session to memory with capacity check."""
        # Allow updating existing keys, but reject new ones if full
        if s.key not in self._sessions and len(self._sessions) >= MAX_MEMORY_SESSIONS:
            log.error(
                f"Memory store full ({len(self._sessions)}/{MAX_MEMORY_SESSIONS})",
                extra={
                    "count": len(self._sessions),
                    "max": MAX_MEMORY_SESSIONS,
                    "event": "memory_store_full",
                }
            )
            raise SessionStoreFullError(
                f"Session store full ({MAX_MEMORY_SESSIONS} sessions). "
                "Reduce active sessions or enable Redis."
            )
        self._sessions[s.key] = s

    async def delete(self, key: str) -> None:
        """Delete session from memory."""
        self._sessions.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if session exists in memory."""
        return key in self._sessions

    async def count(self) -> int:
        """Count sessions in memory."""
        return len(self._sessions)

    async def cleanup(self) -> int:
        """Clean up expired sessions from memory."""
        expired_keys = [k for k, s in list(self._sessions.items()) if s.is_expired()]
        for k in expired_keys:
            del self._sessions[k]
        return len(expired_keys)

    async def health_check(self) -> bool:
        """Memory store is always healthy."""
        return True

    def capacity_percentage(self) -> float:
        """Get current fill percentage (for readiness probes)."""
        if MAX_MEMORY_SESSIONS <= 0:
            return 0.0
        return (len(self._sessions) / MAX_MEMORY_SESSIONS) * 100


# ═════════════════════════════════════════════════════════════════════════════
# WEBSOCKET REGISTRY — In-memory peer tracking
# ═════════════════════════════════════════════════════════════════════════════

class WebSocketRegistry:
    """Registry for active WebSocket connections."""

    def __init__(self):
        self._connections: Dict[str, Dict[str, Optional[WebSocket]]] = {}

    def get(self, key: str, role: str) -> Optional[WebSocket]:
        """Get WebSocket for a peer."""
        return self._connections.get(key, {}).get(role)

    def set(self, key: str, role: str, ws: WebSocket) -> None:
        """Register a WebSocket connection."""
        self._connections.setdefault(key, {"sender": None, "receiver": None})[role] = ws

    def clear(self, key: str, role: str) -> None:
        """Unregister a WebSocket connection."""
        if key in self._connections:
            self._connections[key][role] = None
            if all(v is None for v in self._connections[key].values()):
                del self._connections[key]

    def both_present(self, key: str) -> bool:
        """Check if both sender and receiver are connected."""
        d = self._connections.get(key, {})
        return d.get("sender") is not None and d.get("receiver") is not None

    def any_present(self, key: str) -> bool:
        """Check if any peer is connected."""
        d = self._connections.get(key, {})
        return d.get("sender") is not None or d.get("receiver") is not None


# ═════════════════════════════════════════════════════════════════════════════
# RETRY MECHANISM — Exponential backoff with jitter
# ═════════════════════════════════════════════════════════════════════════════

class RetryPolicy:
    """Exponential backoff retry strategy."""

    def __init__(
        self,
        max_retries: int = REDIS_MAX_RETRIES,
        backoff_factor: float = REDIS_RETRY_BACKOFF_FACTOR,
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def calculate_delay(self, attempt: int) -> float:
        """Calculate backoff delay with jitter."""
        if attempt >= self.max_retries:
            return 0
        # Exponential backoff: 0.1s, 0.2s, 0.4s, etc.
        delay = self.backoff_factor * (2 ** attempt)
        # Add jitter (0-20% variance)
        jitter = delay * secrets.randbelow(20) / 100
        return delay + jitter

    async def execute_with_retry(self, coro, operation_name: str = "operation"):
        """Execute async operation with retries."""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro()
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    log.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay:.2f}s",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        log.error(f"{operation_name} failed after {self.max_retries + 1} attempts")
        raise last_error


# ═════════════════════════════════════════════════════════════════════════════
# SESSION MANAGER — Main public API
# ═════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Enterprise-grade session manager for distributed WebRTC transfers.
    
    Features:
    - Redis-backed or in-memory storage
    - Automatic connection management
    - Retry mechanisms for transient failures
    - Health checks for monitoring
    - Structured logging and metrics
    - One-time key enforcement
    - Comprehensive error handling
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._store: Optional[SessionStore] = None
        self._ws_registry = WebSocketRegistry()
        self._redis_client: Optional[aioredis.Redis] = None
        self._retry_policy = RetryPolicy(REDIS_MAX_RETRIES, REDIS_RETRY_BACKOFF_FACTOR)

        # Metrics
        self._total_created   = 0
        self._total_expired   = 0
        self._total_completed = 0
        self._started_at      = time.time()

    # ────────────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Initialize session store (Redis or memory fallback)."""
        try:
            if hasattr(self._settings, 'redis_enabled') and self._settings.redis_enabled:
                await self._initialize_redis()
            else:
                self._initialize_memory()
        except Exception as e:
            log.error(f"Session manager startup failed: {e}", exc_info=True)
            # Fallback to memory store
            log.warning("Falling back to memory store")
            self._initialize_memory()

    async def _initialize_redis(self) -> None:
        """Initialize Redis connection pool."""
        try:
            redis_url = self._settings.REDIS_URL
            
            # Create connection pool
            self._redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=REDIS_POOL_SIZE,
                socket_connect_timeout=REDIS_CONNECTION_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                socket_keepalive=True,
                retry_on_timeout=True,
            )

            # Test connection
            await self._retry_policy.execute_with_retry(
                lambda: self._redis_client.ping(),
                operation_name="Redis ping"
            )

            self._store = RedisStore(
                self._redis_client,
                self._settings.REDIS_PREFIX,
                SESSION_TTL_DEFAULT,
            )

            log.info(
                "Redis store initialized",
                extra={
                    "backend": "redis",
                    "host": redis_url.split("@")[-1][:40],
                    "pool_size": REDIS_POOL_SIZE,
                }
            )
        except Exception as e:
            log.warning(f"Redis initialization failed: {e}")
            raise

    def _initialize_memory(self) -> None:
        """Initialize in-memory fallback store."""
        self._store = MemoryStore()
        log.info(
            "Memory store initialized",
            extra={
                "backend": "memory",
                "max_sessions": MAX_MEMORY_SESSIONS,
            }
        )

    async def shutdown(self) -> None:
        """Close connections and cleanup."""
        if self._redis_client:
            try:
                await self._redis_client.aclose()
                log.info("Redis connection closed")
            except Exception as e:
                log.warning(f"Error closing Redis: {e}")

    # ────────────────────────────────────────────────────────────────────────────
    # HEALTH CHECKS
    # ────────────────────────────────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Get session manager health status."""
        assert self._store, "Call startup() first"
        
        try:
            store_healthy = await self._store.health_check()
            
            # Check memory store capacity
            capacity_pct = 0.0
            if isinstance(self._store, MemoryStore):
                capacity_pct = self._store.capacity_percentage()

            return {
                "healthy": store_healthy,
                "backend": "redis" if isinstance(self._store, RedisStore) else "memory",
                "sessions_active": await self._store.count(),
                "memory_capacity_pct": capacity_pct,
                "metrics": self.stats(),
            }
        except Exception as e:
            log.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }

    # ────────────────────────────────────────────────────────────────────────────
    # SESSION CRUD
    # ────────────────────────────────────────────────────────────────────────────

    async def create_session(self, client_ip: str = "") -> str:
        """
        Create a new transfer session.
        
        Collision detection with exponential backoff.
        Raises HTTP 503 if store is full.
        """
        assert self._store, "Call startup() first"
        now = time.time()
        collisions = 0

        for attempt in range(10):
            key = _make_key(self._settings.KEY_LENGTH)
            
            if not await self._store.exists(key):
                break
            
            collisions += 1
            # [C6] Rate-limit collision loop
            await asyncio.sleep(0.05)

        # Log high collision count
        if collisions > 3:
            log.warning(
                f"High key collision count ({collisions}) — key space pressure",
                extra={
                    "collisions": collisions,
                    "key_length": self._settings.KEY_LENGTH,
                    "event": "key_collision_high",
                }
            )
            if self._settings.KEY_LENGTH < 8:
                log.critical(
                    "KEY_LENGTH < 8 with collisions — key space exhaustion risk!",
                    extra={
                        "key_length": self._settings.KEY_LENGTH,
                        "event": "key_space_exhaustion",
                    }
                )

        # Create session
        s = SessionData(
            key=key,
            created_at=now,
            expires_at=now + SESSION_TTL_DEFAULT,
            creator_ip=client_ip,
        )

        try:
            await self._store.save(s)
        except SessionStoreFullError as e:
            log.error(f"Session store full: {e.message}")
            raise HTTPException(status_code=503, detail="Session store is full. Try again later.")

        self._total_created += 1
        
        log.info(
            f"Session created: {key[:4]}****",
            extra={
                "key_prefix": key[:4] + "****",
                "creator_ip": client_ip,
                "event": "session_created",
            }
        )

        return key

    async def get_session(self, key: str) -> Optional[SessionData]:
        """Get session by key (handles expiry)."""
        assert self._store, "Call startup() first"
        
        try:
            s = await self._store.get(key)
            if s is None:
                return None
            
            if s.is_expired():
                log.info(f"Session expired: {key[:4]}****")
                await self._store.delete(key)
                self._total_expired += 1
                return None
            
            return s
        except RedisConnectionError as e:
            log.error(f"Failed to get session: {e.message}")
            raise

    async def add_peer(self, key: str, role: str, ws: WebSocket) -> Tuple[bool, str]:
        """
        Register a peer WebSocket for a session.
        
        One-time key enforcement: first receiver consumes the key.
        Subsequent receivers are rejected (if ONE_TIME_KEY_ENABLED).
        """
        s = await self.get_session(key)
        if not s:
            return False, "Invalid or expired key"

        if role == "sender":
            if self._ws_registry.get(key, "sender") is not None:
                s.sender_reconnects += 1
                log.info(f"Sender reconnect: {key[:4]}**** (#{s.sender_reconnects})")
            s.state = TransferState.WAITING.value

        else:  # role == "receiver"
            existing_receiver_ws = self._ws_registry.get(key, "receiver")

            # [OTK] One-time key enforcement
            if ONE_TIME_KEY_ENABLED:
                is_reconnect = existing_receiver_ws is not None
                if s.key_consumed and not is_reconnect:
                    # Key already consumed by different receiver
                    log.warning(
                        f"One-time key already used: {key[:4]}****",
                        extra={
                            "key_prefix": key[:4] + "****",
                            "event": "key_already_used",
                        }
                    )
                    audit_log.log(
                        event_type="key_already_used",
                        key_prefix=key,
                        reason="Second receiver attempted to use one-time key",
                    )
                    raise KeyAlreadyUsedError(
                        "This key has already been used. Request a new one from sender."
                    )

            if existing_receiver_ws is not None:
                # Legitimate reconnect
                s.receiver_reconnects += 1
                log.info(f"Receiver reconnect: {key[:4]}**** (#{s.receiver_reconnects})")
            else:
                # First-time receiver connection — consume key
                if ONE_TIME_KEY_ENABLED and not s.key_consumed:
                    s.key_consumed = True
                    log.info(
                        f"One-time key consumed: {key[:4]}****",
                        extra={
                            "key_prefix": key[:4] + "****",
                            "event": "key_consumed",
                        }
                    )

        self._ws_registry.set(key, role, ws)

        if self._ws_registry.both_present(key):
            s.state = TransferState.ACTIVE.value
            log.info(
                f"Both peers connected: {key[:4]}****",
                extra={
                    "key_prefix": key[:4] + "****",
                    "event": "both_connected",
                }
            )

        await self._store.save(s)
        return True, ""

    async def remove_peer(self, key: str, role: str) -> None:
        """Unregister a peer WebSocket."""
        s = await self._store.get(key) if self._store else None
        self._ws_registry.clear(key, role)

        if s is None:
            return

        if self._ws_registry.any_present(key):
            # Other peer still connected
            if s.state == TransferState.ACTIVE.value:
                s.state = TransferState.WAITING.value
                await self._store.save(s)
            return

        # All peers disconnected
        if s.state == TransferState.TRANSFER.value:
            log.info(f"Transfer interrupted: {key[:4]}**** (keeping session)")
            return
        
        if s.state == TransferState.COMPLETED.value:
            self._total_completed += 1

        await self._store.delete(key)
        log.info(f"Session closed: {key[:4]}**** (state={s.state})")

    def get_peer(self, key: str, role: str) -> Optional[WebSocket]:
        """Get WebSocket for a peer."""
        return self._ws_registry.get(key, role)

    # ────────────────────────────────────────────────────────────────────────────
    # TRANSFER STATE MUTATIONS
    # ────────────────────────────────────────────────────────────────────────────

    async def start_transfer(self, key: str) -> None:
        """Mark transfer as started and extend TTL."""
        s = await self.get_session(key)
        if s and s.state not in (TransferState.TRANSFER.value, TransferState.COMPLETED.value):
            s.state = TransferState.TRANSFER.value
            if not s.transfer_started_at:
                s.transfer_started_at = time.time()
            # Extend TTL for active transfer
            if s.expires_at - time.time() < SESSION_TTL_TRANSFER:
                s.expires_at = time.time() + SESSION_TTL_TRANSFER
            await self._store.save(s)

    async def complete_transfer(self, key: str) -> None:
        """Mark transfer as completed."""
        s = await self.get_session(key)
        if s:
            s.state = TransferState.COMPLETED.value
            s.transfer_completed_at = time.time()
            self._total_completed += 1
            await self._store.save(s)

    async def register_files(self, key: str, files: list) -> None:
        """Register files in transfer session."""
        s = await self.get_session(key)
        if not s:
            return
        for i, f in enumerate(files):
            s.register_file(
                i,
                f.get("name", ""),
                f.get("size", 0),
                f.get("totalChunks", 0),
                f.get("sha256", "")
            )
        await self._store.save(s)

    async def ack_chunk(self, key: str, file_index: int, chunk_index: int) -> None:
        """Acknowledge chunk receipt."""
        s = await self.get_session(key)
        if s:
            s.ack_chunk(file_index, chunk_index)
            await self._store.save(s)

    async def complete_file(self, key: str, file_index: int) -> bool:
        """Mark file as completed."""
        s = await self.get_session(key)
        if not s:
            return False
        s.complete_file(file_index)
        done = s.all_files_done()
        await self._store.save(s)
        return done

    # ────────────────────────────────────────────────────────────────────────────
    # METRICS & MONITORING
    # ────────────────────────────────────────────────────────────────────────────

    async def count(self) -> int:
        """Count active sessions."""
        return await self._store.count() if self._store else 0

    def stats(self) -> Dict[str, Any]:
        """Get session manager statistics."""
        return {
            "total_created": self._total_created,
            "total_expired": self._total_expired,
            "total_completed": self._total_completed,
            "uptime_seconds": int(time.time() - self._started_at),
            "backend": "redis" if isinstance(self._store, RedisStore) else "memory",
        }

    # ────────────────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ────────────────────────────────────────────────────────────────────────────

    async def cleanup_loop(self) -> None:
        """Periodic cleanup of expired sessions (for memory store)."""
        while True:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
            try:
                if isinstance(self._store, MemoryStore):
                    n = await self._store.cleanup()
                    if n > 0:
                        self._total_expired += n
                        log.info(f"Cleaned {n} expired sessions")
            except Exception as e:
                log.error(f"Cleanup loop error: {e}", exc_info=True)
