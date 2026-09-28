"""Threading utilities for background tasks."""

import threading
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def run_in_background(func: Callable[P, T]) -> Callable[P, None]:
    """Decorator to run a function in a background daemon thread.

    Args:
        func: Function to run in background

    Returns:
        Wrapper that starts the function in a daemon thread
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()

    return wrapper


def start_background_task(func: Callable[[], None]) -> threading.Thread:
    """Start a function in a background daemon thread.

    Args:
        func: Function to run (no arguments)

    Returns:
        The started thread
    """
    thread = threading.Thread(target=func, daemon=True)
    thread.start()
    return thread
