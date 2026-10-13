"""Tests for Notion rate limiter."""

import time

import pytest

from app.tools.notion.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_burst_and_throttle():
    # 5 tokens per second, capacity 2
    limiter = TokenBucketRateLimiter(rate=10.0, capacity=2.0)

    # First 2 acquire immediately
    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    burst_elapsed = time.monotonic() - start
    assert burst_elapsed < 0.1

    # 3rd acquire must wait for ~0.1s
    await limiter.acquire()
    total_elapsed = time.monotonic() - start
    assert total_elapsed >= 0.08
