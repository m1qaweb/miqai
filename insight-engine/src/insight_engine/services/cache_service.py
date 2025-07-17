"""
Enhanced Redis-based caching service with comprehensive patterns and monitoring.

This module provides a production-ready caching service with:
- Connection pooling and circuit breaker patterns
- Multiple caching strategies (cache-aside, write-through, etc.)
- Performance metrics and monitoring
- Batch operations and pipeline support
- JSON serialization and compression
- Cache invalidation patterns
"""

import asyncio
import json
import time
import zlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
from pydantic import BaseModel

from insight_engine.logging_config import get_logger
from insight_engine.exceptions import CacheException, RedisConnectionException

logger = get_logger(__name__)

T = TypeVar('T')

# Prometheus metrics for cache monitoring
CACHE_OPERATIONS_TOTAL = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status', 'cache_name']
)

CACHE_OPERATION_DURATION = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration',
    ['operation', 'cache_name']
)

CACHE_HIT_RATIO = Gauge(
    'cache_hit_ratio',
    'Cache hit ratio',
    ['cache_name']
)

CACHE_MEMORY_USAGE = Gauge(
    'cache_memory_usage_bytes',
    'Cache memory usage in bytes',
    ['cache_name']
)

CACHE_CONNECTIONS_ACTIVE = Gauge(
    'cache_connections_active',
    'Active cache connections',
    ['cache_name']
)


class CacheStrategy(Enum):
    """Cache strategy enumeration."""
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


@dataclass
class CacheConfig:
    """Cache configuration settings."""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    max_connections: int = 20
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    default_ttl: int = 3600
    compression_threshold: int = 1024  # Compress values larger than 1KB
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    success_count: int = 0


class CacheItem(BaseModel, Generic[T]):
    """Cache item wrapper with metadata."""
    value: T
    created_at: datetime
    ttl: int
    hit_count: int = 0
    compressed: bool = False


class EnhancedCacheService:
    """
    Enhanced Redis-based caching service with comprehensive features.
    
    Features:
    - Connection pooling with health monitoring
    - Circuit breaker pattern for resilience
    - Multiple caching strategies
    - Performance metrics and monitoring
    - JSON serialization with compression
    - Batch operations and pipelining
    - Cache invalidation patterns
    """
    
    def __init__(self, config: CacheConfig, cache_name: str = "default"):
        self.config = config
        self.cache_name = cache_name
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._circuit_breaker = CircuitBreakerStats()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'total_operations': 0
        }
        self._last_health_check = 0
        self._is_healthy = True
        
    async def initialize(self) -> None:
        """Initialize the cache service with connection pool."""
        try:
            self._pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                decode_responses=False  # We'll handle encoding ourselves
            )
            
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            
            logger.info(
                f"Cache service '{self.cache_name}' initialized successfully",
                extra={
                    "cache_name": self.cache_name,
                    "host": self.config.host,
                    "port": self.config.port,
                    "max_connections": self.config.max_connections
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to initialize cache service '{self.cache_name}'",
                extra={"error": str(e), "cache_name": self.cache_name}
            )
            raise CacheException(f"Cache initialization failed: {e}")
    
    async def close(self) -> None:
        """Close the cache service and cleanup connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        
        logger.info(f"Cache service '{self.cache_name}' closed")
    
    @asynccontextmanager
    async def _circuit_breaker_context(self, operation: str):
        """Context manager for circuit breaker pattern."""
        if self._circuit_breaker.state == CircuitBreakerState.OPEN:
            if (time.time() - (self._circuit_breaker.last_failure_time or 0) 
                > self.config.circuit_breaker_recovery_timeout):
                self._circuit_breaker.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker for '{self.cache_name}' moved to HALF_OPEN")
            else:
                CACHE_OPERATIONS_TOTAL.labels(
                    operation=operation, 
                    status='circuit_breaker_open', 
                    cache_name=self.cache_name
                ).inc()
                raise CacheException("Circuit breaker is OPEN")
        
        start_time = time.time()
        try:
            yield
            
            # Success - reset circuit breaker if needed
            if self._circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
                self._circuit_breaker.state = CircuitBreakerState.CLOSED
                self._circuit_breaker.failure_count = 0
                logger.info(f"Circuit breaker for '{self.cache_name}' moved to CLOSED")
            
            self._circuit_breaker.success_count += 1
            CACHE_OPERATIONS_TOTAL.labels(
                operation=operation, 
                status='success', 
                cache_name=self.cache_name
            ).inc()
            
        except Exception as e:
            # Failure - update circuit breaker
            self._circuit_breaker.failure_count += 1
            self._circuit_breaker.last_failure_time = time.time()
            
            if (self._circuit_breaker.failure_count >= 
                self.config.circuit_breaker_failure_threshold):
                self._circuit_breaker.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker for '{self.cache_name}' moved to OPEN")
            
            CACHE_OPERATIONS_TOTAL.labels(
                operation=operation, 
                status='error', 
                cache_name=self.cache_name
            ).inc()
            raise
        
        finally:
            duration = time.time() - start_time
            CACHE_OPERATION_DURATION.labels(
                operation=operation, 
                cache_name=self.cache_name
            ).observe(duration)
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize and optionally compress a value."""
        if isinstance(value, (str, int, float, bool)):
            serialized = str(value).encode('utf-8')
        else:
            serialized = json.dumps(value, default=str).encode('utf-8')
        
        # Compress if value is large enough
        if len(serialized) > self.config.compression_threshold:
            compressed = zlib.compress(serialized)
            # Only use compression if it actually reduces size
            if len(compressed) < len(serialized):
                return b'COMPRESSED:' + compressed
        
        return serialized
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize and optionally decompress a value."""
        if data.startswith(b'COMPRESSED:'):
            data = zlib.decompress(data[11:])  # Remove 'COMPRESSED:' prefix
        
        try:
            # Try to decode as JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to string
            return data.decode('utf-8')
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        async with self._circuit_breaker_context('get'):
            try:
                data = await self._client.get(key)
                if data is None:
                    self._stats['misses'] += 1
                    return None
                
                self._stats['hits'] += 1
                return self._deserialize_value(data)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache GET error for key '{key}': {e}")
                raise CacheException(f"Cache GET failed: {e}")
            finally:
                self._stats['total_operations'] += 1
                self._update_hit_ratio()
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set a value in cache with optional TTL."""
        async with self._circuit_breaker_context('set'):
            try:
                ttl = ttl or self.config.default_ttl
                serialized_value = self._serialize_value(value)
                
                if ttl > 0:
                    result = await self._client.setex(key, ttl, serialized_value)
                else:
                    result = await self._client.set(key, serialized_value)
                
                return bool(result)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache SET error for key '{key}': {e}")
                raise CacheException(f"Cache SET failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Cache-aside pattern: get from cache or set using factory function.
        """
        # Try to get from cache first
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Cache miss - generate value and cache it
        try:
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            
            await self.set(key, value, ttl)
            return value
            
        except Exception as e:
            logger.error(f"Factory function failed for key '{key}': {e}")
            raise
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        async with self._circuit_breaker_context('delete'):
            try:
                result = await self._client.delete(key)
                return bool(result)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache DELETE error for key '{key}': {e}")
                raise CacheException(f"Cache DELETE failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        async with self._circuit_breaker_context('exists'):
            try:
                result = await self._client.exists(key)
                return bool(result)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache EXISTS error for key '{key}': {e}")
                raise CacheException(f"Cache EXISTS failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        async with self._circuit_breaker_context('increment'):
            try:
                result = await self._client.incrby(key, amount)
                return int(result)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache INCREMENT error for key '{key}': {e}")
                raise CacheException(f"Cache INCREMENT failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for an existing key."""
        async with self._circuit_breaker_context('expire'):
            try:
                result = await self._client.expire(key, ttl)
                return bool(result)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache EXPIRE error for key '{key}': {e}")
                raise CacheException(f"Cache EXPIRE failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        async with self._circuit_breaker_context('invalidate_pattern'):
            try:
                keys = await self._client.keys(pattern)
                if keys:
                    result = await self._client.delete(*keys)
                    logger.info(f"Invalidated {result} keys matching pattern '{pattern}'")
                    return result
                return 0
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache INVALIDATE_PATTERN error for pattern '{pattern}': {e}")
                raise CacheException(f"Cache INVALIDATE_PATTERN failed: {e}")
            finally:
                self._stats['total_operations'] += 1
    
    async def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache in a single operation."""
        async with self._circuit_breaker_context('get_multiple'):
            try:
                if not keys:
                    return {}
                
                values = await self._client.mget(keys)
                result = {}
                
                for key, value in zip(keys, values):
                    if value is not None:
                        result[key] = self._deserialize_value(value)
                        self._stats['hits'] += 1
                    else:
                        self._stats['misses'] += 1
                
                return result
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache GET_MULTIPLE error: {e}")
                raise CacheException(f"Cache GET_MULTIPLE failed: {e}")
            finally:
                self._stats['total_operations'] += len(keys)
                self._update_hit_ratio()
    
    async def set_multiple(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache."""
        async with self._circuit_breaker_context('set_multiple'):
            try:
                if not mapping:
                    return True
                
                # Serialize all values
                serialized_mapping = {
                    key: self._serialize_value(value)
                    for key, value in mapping.items()
                }
                
                # Use pipeline for atomic operation
                async with self._client.pipeline() as pipe:
                    await pipe.mset(serialized_mapping)
                    
                    # Set TTL for all keys if specified
                    if ttl and ttl > 0:
                        for key in mapping.keys():
                            await pipe.expire(key, ttl)
                    
                    results = await pipe.execute()
                    return all(results)
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Cache SET_MULTIPLE error: {e}")
                raise CacheException(f"Cache SET_MULTIPLE failed: {e}")
            finally:
                self._stats['total_operations'] += len(mapping)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache service."""
        current_time = time.time()
        
        # Skip if recently checked
        if (current_time - self._last_health_check < 
            self.config.health_check_interval):
            return self._get_health_status()
        
        try:
            start_time = time.time()
            
            # Test basic operations
            test_key = f"health_check:{self.cache_name}:{current_time}"
            await self._client.set(test_key, "health_check", ex=60)
            value = await self._client.get(test_key)
            await self._client.delete(test_key)
            
            response_time = time.time() - start_time
            
            # Get Redis info
            info = await self._client.info()
            
            self._is_healthy = True
            self._last_health_check = current_time
            
            # Update Prometheus metrics
            CACHE_CONNECTIONS_ACTIVE.labels(cache_name=self.cache_name).set(
                info.get('connected_clients', 0)
            )
            CACHE_MEMORY_USAGE.labels(cache_name=self.cache_name).set(
                info.get('used_memory', 0)
            )
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'last_check': datetime.fromtimestamp(current_time),
                'circuit_breaker_state': self._circuit_breaker.state.value,
                'stats': self._stats.copy(),
                'redis_info': {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                }
            }
            
        except Exception as e:
            self._is_healthy = False
            logger.error(f"Cache health check failed for '{self.cache_name}': {e}")
            
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.fromtimestamp(current_time),
                'circuit_breaker_state': self._circuit_breaker.state.value,
                'stats': self._stats.copy()
            }
    
    def _get_health_status(self) -> Dict[str, Any]:
        """Get current health status without performing checks."""
        return {
            'status': 'healthy' if self._is_healthy else 'unhealthy',
            'last_check': datetime.fromtimestamp(self._last_health_check),
            'circuit_breaker_state': self._circuit_breaker.state.value,
            'stats': self._stats.copy()
        }
    
    def _update_hit_ratio(self) -> None:
        """Update cache hit ratio metric."""
        total_requests = self._stats['hits'] + self._stats['misses']
        if total_requests > 0:
            hit_ratio = self._stats['hits'] / total_requests
            CACHE_HIT_RATIO.labels(cache_name=self.cache_name).set(hit_ratio)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_ratio = (self._stats['hits'] / total_requests) if total_requests > 0 else 0
        
        return {
            'cache_name': self.cache_name,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'errors': self._stats['errors'],
            'total_operations': self._stats['total_operations'],
            'hit_ratio': hit_ratio,
            'circuit_breaker_state': self._circuit_breaker.state.value,
            'circuit_breaker_failures': self._circuit_breaker.failure_count,
            'is_healthy': self._is_healthy
        }


# Global cache service instances
_cache_services: Dict[str, EnhancedCacheService] = {}


async def get_cache_service(
    cache_name: str = "default",
    config: Optional[CacheConfig] = None
) -> EnhancedCacheService:
    """Get or create a cache service instance."""
    if cache_name not in _cache_services:
        if config is None:
            # Use default configuration
            from insight_engine.config import settings
            config = CacheConfig(
                host=str(settings.REDIS_DSN).split('@')[-1].split('/')[0].split(':')[0],
                port=int(str(settings.REDIS_DSN).split('@')[-1].split('/')[0].split(':')[1]) if ':' in str(settings.REDIS_DSN).split('@')[-1].split('/')[0] else 6379,
                db=int(str(settings.REDIS_DSN).split('/')[-1]) if '/' in str(settings.REDIS_DSN) else 0
            )
        
        service = EnhancedCacheService(config, cache_name)
        await service.initialize()
        _cache_services[cache_name] = service
    
    return _cache_services[cache_name]


async def close_all_cache_services() -> None:
    """Close all cache service instances."""
    for service in _cache_services.values():
        await service.close()
    _cache_services.clear()