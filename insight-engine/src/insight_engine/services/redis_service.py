import os
import redis.asyncio as redis
from typing import Optional
from google.api_core import exceptions
from insight_engine.dependencies import get_secret

class RedisService:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        try:
            self.redis_password = get_secret("redis-password")
        except exceptions.NotFound:
            self.redis_password = None  # Fallback for local dev without secret

        self.client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=True,  # Decode responses to UTF-8
        )

    async def get(self, key: str) -> Optional[str]:
        """
        Retrieves a value from the cache asynchronously.
        """
        try:
            return await self.client.get(key)
        except redis.ConnectionError as e:
            # Log the error, but don't crash the app
            print(f"Redis connection error: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        """
        Sets a value in the cache with a TTL asynchronously.
        """
        try:
            await self.client.setex(key, ttl, value)
        except redis.ConnectionError as e:
            # Log the error, but don't crash the app
            print(f"Redis connection error: {e}")

# Singleton instance for dependency injection
redis_service = RedisService()

def get_redis_service() -> RedisService:
    return redis_service