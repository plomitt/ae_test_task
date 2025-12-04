"""Rate limiting implementation."""

import logging
import time
from typing import Optional

import redis.asyncio as redis

from yr_forecast.config import (
    REDIS_URL,
    RATE_LIMIT_REQUESTS_PER_SECOND,
    RATE_LIMIT_REDIS_KEY_PREFIX
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using Redis sorted set algorithm.

    Tracks requests per second using Redis.
    Allows requests if Redis is unavailable.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize rate limiter.

        Args:
            redis_client: Optional Redis client. If None, creates new client.
        """
        self.redis_client = redis_client or redis.from_url(REDIS_URL)
        self.max_requests = RATE_LIMIT_REQUESTS_PER_SECOND
        self.key_prefix = RATE_LIMIT_REDIS_KEY_PREFIX
        self.sorted_set_key = f"{self.key_prefix}:global" # Use a single global key for sorted set
        self.window_size = 1.0  # 1 second window

    async def is_allowed(self) -> tuple[bool, int]:
        """Check if a request is allowed under the rate limit.

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if request should be allowed
            - retry_after_seconds: Seconds to wait before retrying (0 if allowed)
        """
        try:
            current_time = time.time()
            # Use microseconds
            current_timestamp = int(current_time * 1000000)
            window_start = (current_time - self.window_size) * 1000000

            # Init pipeline
            pipe = self.redis_client.pipeline()

            # Add current request timestamp
            pipe.zadd(self.sorted_set_key, {str(current_timestamp): current_timestamp})

            # Remove old entries outside the window
            pipe.zremrangebyscore(self.sorted_set_key, 0, window_start)

            # Count current requests in window
            pipe.zcard(self.sorted_set_key)

            # Set expiration
            pipe.expire(self.sorted_set_key, int(self.window_size * 2))

            _, _, request_count, _ = await pipe.execute()

            # Check if rate limited
            if request_count > self.max_requests:
                retry_after = 2

                logger.debug(f"Rate limited: count={request_count}, max={self.max_requests}, retry_after={retry_after}")
                return False, retry_after
            else:
                logger.debug(f"Not rate limited: count={request_count}, max={self.max_requests}")
                return True, 0

        except Exception as e:
            # Allow request if Redis is down
            logger.error(f"Rate limiter error: {e}")
            return True, 0

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()