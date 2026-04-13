"""Performance monitoring utilities for measuring execution time"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional

# Default logger for this module
_default_logger = logging.getLogger(__name__)


def measure_time_sync(method_name: str) -> Callable:
    """
    Decorator to measure execution time of synchronous methods.

    Usage:
        @measure_time_sync("MyClass.my_method")
        def my_method(self):
            pass

    Args:
        method_name: Name to display in the log (e.g., "ClassName.method_name")

    Returns:
        Decorated function that logs execution time
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            _default_logger.info(f"⏱️ {method_name}: {duration:.2f}ms")
            return result

        return wrapper

    return decorator


def measure_time_async(method_name: str) -> Callable:
    """
    Decorator to measure execution time of asynchronous methods.

    Usage:
        @measure_time_async("MyClass.my_method")
        async def my_method(self):
            pass

    Args:
        method_name: Name to display in the log (e.g., "ClassName.method_name")

    Returns:
        Decorated async function that logs execution time
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            _default_logger.info(f"⏱️ {method_name}: {duration:.2f}ms")
            return result

        return wrapper

    return decorator


def patch_method_timing(
    obj: Any,
    method_name: str,
    display_name: str,
    is_async: bool = False,
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Monkey-patch a method to add timing measurement without modifying its source.

    Usage:
        # For sync methods
        patch_method_timing(embed_model, "get_query_embedding", "OpenAI.get_embedding", is_async=False, logger=my_logger)

        # For async methods
        patch_method_timing(vector_store, "query", "PGVectorStore.query", is_async=True, logger=my_logger)

    Args:
        obj: Object instance or class to patch
        method_name: Name of the method to patch
        display_name: Name to display in logs
        is_async: Whether the method is async or not
        logger: Optional logger to use. If None, uses default module logger.
    """
    # Use provided logger or default
    log = logger or _default_logger

    # Get the class if obj is an instance
    target_class = obj if isinstance(obj, type) else obj.__class__

    # Get the original unbound method from the class
    original_method = getattr(target_class, method_name)

    # Check if it's an unbound method (callable) or a descriptor
    if not callable(original_method):
        raise ValueError(f"Cannot patch {method_name}: not a callable method")

    if is_async:

        async def async_timed_method(self, *args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            # Call the original method as a bound method
            result = await original_method(self, *args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            log.info(f"⏱️ {display_name}: {duration:.2f}ms")
            return result

        # Copy over attributes for proper wrapping
        async_timed_method.__name__ = original_method.__name__
        async_timed_method.__doc__ = original_method.__doc__
        setattr(target_class, method_name, async_timed_method)
    else:

        def sync_timed_method(self, *args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            # Call the original method as a bound method
            result = original_method(self, *args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            log.info(f"⏱️ {display_name}: {duration:.2f}ms")
            return result

        # Copy over attributes for proper wrapping
        sync_timed_method.__name__ = original_method.__name__
        sync_timed_method.__doc__ = original_method.__doc__
        setattr(target_class, method_name, sync_timed_method)
