"""Redis client for rate limiting and caching."""
import redis
import os
import logging
from typing import Optional, Union
import json
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))


class RedisClient:
    """Redis client wrapper with connection pooling."""
    
    def __init__(self):
        try:
            self.pool = redis.ConnectionPool.from_url(
                REDIS_URL,
                max_connections=REDIS_MAX_CONNECTIONS,
                decode_responses=True
            )
            self.client = redis.Redis(connection_pool=self.pool)
            # Test connection
            self.client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Union[str, dict], ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL in seconds."""
        try:
            if isinstance(value, dict):
                value = json.dumps(value)
            
            if ttl:
                return self.client.setex(key, ttl, value)
            else:
                return self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def incr(self, key: str) -> Optional[int]:
        """Increment counter."""
        try:
            return self.client.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            return None
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for a key."""
        try:
            return self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[dict]:
        """Get and decode JSON value."""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key {key}")
        return None
    
    def rate_limit_check(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Check rate limit for a key.
        
        Args:
            key: Rate limit key (e.g., "vote:user:123")
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_count)
        """
        try:
            current = self.incr(key)
            if current == 1:
                self.expire(key, window)
            
            remaining = max(0, limit - current)
            return current <= limit, remaining
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Allow request on error to prevent blocking users
            return True, limit
    
    def close(self):
        """Close Redis connection pool."""
        try:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Create singleton instance
redis_client = RedisClient()