"""Retry decorator with exponential backoff."""

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar, cast

from src.config import settings
from src.utils.exceptions import RetryableError
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int | None = None,
    initial_delay: float | None = None,
    max_delay: float | None = None,
    multiplier: float | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: from settings)
        initial_delay: Initial delay in seconds (default: from settings)
        max_delay: Maximum delay in seconds (default: from settings)
        multiplier: Backoff multiplier (default: from settings)
        retryable_exceptions: Tuple of exception types to retry

    Returns:
        Decorated function with retry logic
    """
    # Use settings defaults if not provided
    _max_retries = max_retries if max_retries is not None else settings.max_retries
    _initial_delay = (
        initial_delay if initial_delay is not None else settings.retry_initial_delay_seconds
    )
    _max_delay = max_delay if max_delay is not None else settings.retry_max_delay_seconds
    _multiplier = multiplier if multiplier is not None else settings.retry_multiplier

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            """Synchronous retry wrapper."""
            last_exception: Exception | None = None

            for attempt in range(_max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < _max_retries:
                        delay = min(_initial_delay * (_multiplier ** attempt), _max_delay)
                        logger.warning(
                            "Retryable error occurred, retrying",
                            attempt=attempt + 1,
                            max_retries=_max_retries,
                            delay_seconds=delay,
                            error=str(e),
                            function=func.__name__,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "Max retries exceeded",
                            max_retries=_max_retries,
                            error=str(e),
                            function=func.__name__,
                        )

            # Re-raise last exception if all retries failed
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic failed unexpectedly")

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            """Asynchronous retry wrapper."""
            last_exception: Exception | None = None

            for attempt in range(_max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < _max_retries:
                        delay = min(_initial_delay * (_multiplier ** attempt), _max_delay)
                        logger.warning(
                            "Retryable error occurred, retrying",
                            attempt=attempt + 1,
                            max_retries=_max_retries,
                            delay_seconds=delay,
                            error=str(e),
                            function=func.__name__,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "Max retries exceeded",
                            max_retries=_max_retries,
                            error=str(e),
                            function=func.__name__,
                        )

            # Re-raise last exception if all retries failed
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic failed unexpectedly")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)

    return decorator
