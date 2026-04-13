"""
Utility Decorators for LiveKit Agent

Provides decorators for dynamic docstring injection and other utilities.
"""

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def with_docstring(doc: str) -> Callable[[F], F]:
    """
    Decorator to inject a docstring into a function.

    IMPORTANT: When used with @function_tool, this decorator MUST come AFTER
    @function_tool in the decorator stack (which means it runs BEFORE).

    Correct usage:
        @function_tool          # Runs SECOND - reads __doc__
        @with_docstring(DOC)    # Runs FIRST - sets __doc__
        async def my_tool():
            pass

    Args:
        doc: The docstring to inject

    Returns:
        Decorator function that sets __doc__ on the wrapped function
    """

    def decorator(func: F) -> F:
        func.__doc__ = doc
        return func

    return decorator
