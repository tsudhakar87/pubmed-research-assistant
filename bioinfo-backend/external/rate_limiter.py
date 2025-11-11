"""
Rate limiter for NCBI E-utilities API
NCBI guidelines: 3 requests/second without API key, 10 requests/second with API key
"""
import asyncio
import time
from typing import Optional
from collections import deque


class RateLimiter:
    """Token bucket rate limiter for API calls"""

    def __init__(self, requests_per_second: float = 3.0):
        """
        Initialize rate limiter

        Args:
            requests_per_second: Maximum number of requests per second (default 3 for NCBI without API key)
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Optional[float] = None
        self._lock = asyncio.Lock()

        # Track request history for monitoring
        self.request_times = deque(maxlen=100)

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks until it's safe to proceed according to rate limit.
        """
        async with self._lock:
            current_time = time.time()

            if self.last_request_time is not None:
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.min_interval:
                    sleep_time = self.min_interval - time_since_last
                    await asyncio.sleep(sleep_time)
                    current_time = time.time()

            self.last_request_time = current_time
            self.request_times.append(current_time)

    def get_current_rate(self) -> float:
        """
        Get the current request rate over the last second

        Returns:
            Current requests per second
        """
        if len(self.request_times) < 2:
            return 0.0

        current_time = time.time()
        # Count requests in the last second
        recent_requests = sum(1 for t in self.request_times if current_time - t <= 1.0)
        return recent_requests

    def reset(self) -> None:
        """Reset the rate limiter state"""
        self.last_request_time = None
        self.request_times.clear()


class NCBIRateLimiter(RateLimiter):
    """Specialized rate limiter for NCBI E-utilities"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NCBI rate limiter

        Args:
            api_key: NCBI API key. If provided, allows 10 req/s, otherwise 3 req/s
        """
        requests_per_second = 10.0 if api_key else 3.0
        super().__init__(requests_per_second)
        self.api_key = api_key