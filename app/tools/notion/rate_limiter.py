"""Token bucket rate limiter for Notion API (~3 requests/second)."""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Thread-safe and async-safe token bucket rate limiter."""

    def __init__(self, rate: float = 3.0, capacity: float = 3.0) -> None:
        """
        Args:
            rate: Tokens added per second.
            capacity: Maximum number of burst tokens.
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available before returning."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate wait time for the next token
                needed = 1.0 - self.tokens
                wait_time = needed / self.rate
                await asyncio.sleep(wait_time)


# Global rate limiter instance
notion_rate_limiter = TokenBucketRateLimiter(rate=3.0, capacity=3.0)
