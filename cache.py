# ═════════════════════════════════════════════════════════════════════════════
# cache.py — Redis Cache Abstraction Layer
#
# Provides a high-level interface for Redis caching operations
# Layer: Infrastructure (Caching)
# ═════════════════════════════════════════════════════════════════════════════

import json
import pickle
from typing import Any, Optional, List
from datetime import timedelta
import asyncio

import aioredis
from aioredis import Redis

from logging_config import StructuredLogger

logger = StructuredLogger(__name__)


class CacheManager:
    """
    Redis cache manager with high-level operations.
    
    Features:
        - Async Redis operations
        - Automatic serialization (JSON/pickle)
        - TTL management
        - Key namespacing
        - Connection pooling
        - Error handling
    
    Example:
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        await cache.set("user:123", {"name": "John"}, ttl=3600)
        user = await cache.get("user:123")
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 3600,
        max_connections: int = 10,
        namespace: str = "dropkey",
    ):
        """
        Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            max_connections: Maximum connection pool size
            namespace: Key namespace prefix
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.namespace = namespace
        self.redis: Optional[Redis] = None
        self.is_connected = False

    async def connect(self) -> None:
        """
        Connect to Redis.
        
        Raises:
            RuntimeError: If connection fails
        """
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf8",
                decode_responses=False,
                max_connections=self.max_connections,
            )
            
            # Test connection
            await self.redis.ping()
            self.is_connected = True
            
            logger.info(
                "Connected to Redis cache",
                redis_url=self.redis_url,
                namespace=self.namespace,
            )
        except Exception as e:
            logger.error(
                "Failed to connect to Redis",
                error=str(e),
                redis_url=self.redis_url,
            )
            raise RuntimeError(f"Redis connection failed: {str(e)}")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.is_connected = False
            logger.info("Disconnected from Redis cache")

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self.namespace}:{key}"

    async def get(self, key: str, deserialize: bool = True) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            deserialize: Auto-deserialize JSON/pickle
        
        Returns:
            Cached value or None if not found
        """
        if not self.is_connected:
            return None
        
        try:
            full_key = self._make_key(key)
            value = await self.redis.get(full_key)
            
            if value is None:
                return None
            
            if deserialize:
                # Try JSON first
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Fall back to pickle
                    return pickle.loads(value)
            
            return value
        
        except Exception as e:
            logger.error(
                "Cache get error",
                key=key,
                error=str(e),
            )
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
            serialize: Auto-serialize to JSON/pickle
        
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            full_key = self._make_key(key)
            ttl = ttl or self.default_ttl
            
            if serialize:
                # Try JSON first
                try:
                    value = json.dumps(value)
                except (TypeError, ValueError):
                    # Fall back to pickle
                    value = pickle.dumps(value)
            
            await self.redis.set(full_key, value, ex=ttl)
            return True
        
        except Exception as e:
            logger.error(
                "Cache set error",
                key=key,
                error=str(e),
            )
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted
        """
        if not self.is_connected:
            return False
        
        try:
            full_key = self._make_key(key)
            result = await self.redis.delete(full_key)
            return result > 0
        
        except Exception as e:
            logger.error(
                "Cache delete error",
                key=key,
                error=str(e),
            )
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if exists
        """
        if not self.is_connected:
            return False
        
        try:
            full_key = self._make_key(key)
            return await self.redis.exists(full_key) > 0
        
        except Exception as e:
            logger.error(
                "Cache exists error",
                key=key,
                error=str(e),
            )
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration on key.
        
        Args:
            key: Cache key
            ttl: TTL in seconds
        
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            full_key = self._make_key(key)
            result = await self.redis.expire(full_key, ttl)
            return result > 0
        
        except Exception as e:
            logger.error(
                "Cache expire error",
                key=key,
                error=str(e),
            )
            return False

    async def ttl(self, key: str) -> int:
        """
        Get TTL for key.
        
        Args:
            key: Cache key
        
        Returns:
            TTL in seconds, -1 if no expiry, -2 if not exists
        """
        if not self.is_connected:
            return -2
        
        try:
            full_key = self._make_key(key)
            return await self.redis.ttl(full_key)
        
        except Exception as e:
            logger.error(
                "Cache ttl error",
                key=key,
                error=str(e),
            )
            return -2

    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Get multiple values.
        
        Args:
            keys: List of cache keys
        
        Returns:
            List of values
        """
        if not self.is_connected:
            return [None] * len(keys)
        
        try:
            full_keys = [self._make_key(k) for k in keys]
            values = await self.redis.mget(full_keys)
            
            result = []
            for value in values:
                if value is None:
                    result.append(None)
                else:
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        result.append(pickle.loads(value))
            
            return result
        
        except Exception as e:
            logger.error(
                "Cache mget error",
                error=str(e),
            )
            return [None] * len(keys)

    async def clear_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern.
        
        Args:
            pattern: Key pattern (e.g., "session:*")
        
        Returns:
            Number of keys deleted
        """
        if not self.is_connected:
            return 0
        
        try:
            full_pattern = self._make_key(pattern)
            keys = await self.redis.keys(full_pattern)
            
            if not keys:
                return 0
            
            return await self.redis.delete(*keys)
        
        except Exception as e:
            logger.error(
                "Cache clear_pattern error",
                pattern=pattern,
                error=str(e),
            )
            return 0

    async def clear(self) -> bool:
        """
        Clear all keys in namespace.
        
        Returns:
            True if successful
        """
        return await self.clear_pattern("*") > 0

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter.
        
        Args:
            key: Cache key
            amount: Amount to increment
        
        Returns:
            New value
        """
        if not self.is_connected:
            return None
        
        try:
            full_key = self._make_key(key)
            return await self.redis.incrby(full_key, amount)
        
        except Exception as e:
            logger.error(
                "Cache incr error",
                key=key,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """
        Check Redis health.
        
        Returns:
            True if healthy
        """
        if not self.is_connected:
            return False
        
        try:
            await self.redis.ping()
            return True
        
        except Exception:
            return False
