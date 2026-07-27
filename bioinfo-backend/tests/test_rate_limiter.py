"""Unit tests for NCBI rate limiter."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import time
import pytest

from src.external.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        limiter = RateLimiter(requests_per_second=10)

        async def run():
            # Should complete quickly (well within 1s) for 5 requests at 10 rps
            start = time.time()
            for _ in range(5):
                await limiter.acquire()
            elapsed = time.time() - start
            assert elapsed < 2.0  # loose bound

        asyncio.run(run())

    def test_rate_limiter_throttles_at_limit(self):
        limiter = RateLimiter(requests_per_second=3)

        async def run():
            # 4 requests at 3/s means we should wait at least ~0.3s
            start = time.time()
            for _ in range(4):
                await limiter.acquire()
            elapsed = time.time() - start
            # With 3 req/s, 4th request must wait ~0.33s after first burst
            assert elapsed >= 0.2  # generous lower bound

        asyncio.run(run())
