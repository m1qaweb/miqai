import os
import redis.asyncio as redis
from typing import Optional
import logging
from google.api_core import exceptions
from insight_engine.dependencies import get_secret
from insight_engine.resilience import database_resilient

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self) -> None:
        self.redis_host: str = os.getenv("REDIS_HOST", "localhost")
        self.redis_port: int = int(os.getenv("REDIS_PORT", 6379))
        try:
            self.redis_password: Optional[str] = get_secret("redis-password")
        except exceptions.NotFound:
            self.redis_password = None  # Fallback for local dev without secret

        self.client: redis.Redis = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=True,  # Decode responses to UTF-8
        )

    @database_resilient("redis_get", fallback=lambda *args, **kwargs: None)
    async def get(self, key: str) -> Optional[str]:
        """
        Retrieves a value from the cache asynchronously with resilience patterns.
        """
        return await self.client.get(key)

    @database_resilient("redis_set", fallback=lambda *args, **kwargs: None)
    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """
        Sets a value in the cache with a TTL asynchronously with resilience patterns.
        """
        await self.client.setex(key, ttl, value)
        
    @database_resilient("redis_delete", fallback=lambda *args, **kwargs: False)
    async def delete(self, key: str) -> bool:
        """
        Deletes a key from the cache with resilience patterns.
        """
        result = await self.client.delete(key)
        return bool(result)
        
    @database_resilient("redis_exists", fallback=lambda *args, **kwargs: False)
    async def exists(self, key: str) -> bool:
        """
        Checks if a key exists in the cache with resilience patterns.
        """
        result = await self.client.exists(key)
        return bool(result)

# Singleton instance for dependency injection
redis_service = RedisService()

def get_redis_service() -> RedisService:
    return redis_service