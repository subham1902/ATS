"""Bounded retry coordinator for idempotent Upstox reads only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import RateLimitClass, RateLimitPolicy


@dataclass(frozen=True, slots=True)
class ReadAttemptResult:
    status_code: int
    retry_after_ms: int | None = None


class ReadRateLimitExhausted(RuntimeError):
    def __init__(self, rate_limit_class: RateLimitClass, status_code: int) -> None:
        self.rate_limit_class = rate_limit_class
        self.status_code = status_code
        super().__init__("bounded read request attempts exhausted")


class ReadRequestCoordinator:
    """Retry only explicitly idempotent reads; never accepts an execution operation."""

    def __init__(
        self,
        policies: tuple[RateLimitPolicy, ...],
        *,
        wait: Callable[[float], None],
    ) -> None:
        self._policies = {item.rate_limit_class: item for item in policies}
        if len(self._policies) != len(policies):
            raise ValueError("duplicate rate-limit policy")
        self._wait = wait

    def execute_read(
        self,
        rate_limit_class: RateLimitClass,
        operation: Callable[[int], ReadAttemptResult],
    ) -> ReadAttemptResult:
        if rate_limit_class is RateLimitClass.NEVER_CALL:
            raise ValueError("execution capability cannot enter read retry coordinator")
        policy = self._policies[rate_limit_class]
        last = ReadAttemptResult(status_code=0)
        for attempt in range(1, policy.maximum_attempts + 1):
            last = operation(policy.timeout_ms)
            retryable = last.status_code == 429 or last.status_code >= 500
            if not retryable:
                return last
            if attempt < policy.maximum_attempts:
                exponential = policy.base_backoff_ms * (2 ** (attempt - 1))
                delay_ms = min(
                    policy.maximum_backoff_ms,
                    max(exponential, last.retry_after_ms or 0),
                )
                self._wait(delay_ms / 1000)
        raise ReadRateLimitExhausted(rate_limit_class, last.status_code)


__all__ = ["ReadAttemptResult", "ReadRateLimitExhausted", "ReadRequestCoordinator"]
