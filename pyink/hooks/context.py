from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyink.fiber import Fiber

# The currently-rendering fiber. Set by the reconciler before calling component_fn.
_current_fiber: ContextVar[Fiber | None] = ContextVar("_current_fiber", default=None)

# The reconciler's schedule_update callback.
_schedule_update: ContextVar[Callable | None] = ContextVar(
    "_schedule_update", default=None
)

# The current app context.
_current_app: ContextVar[Any] = ContextVar("_current_app", default=None)


def get_current_fiber() -> Fiber:
    """Get the currently-rendering fiber from context.

    Returns
    -------
    Fiber
        The fiber that is currently being rendered.

    Raises
    ------
    RuntimeError
        If called outside of a component render.
    """
    fiber = _current_fiber.get()
    if fiber is None:
        raise RuntimeError("Hook called outside of a component render")
    return fiber


def get_schedule_update() -> Callable:
    """Get the reconciler's schedule_update callback from context.

    Returns
    -------
    Callable
        The schedule_update function provided by the reconciler.

    Raises
    ------
    RuntimeError
        If no reconciler is available.
    """
    fn = _schedule_update.get()
    if fn is None:
        raise RuntimeError("No reconciler available")
    return fn


def get_current_app() -> Any:
    """Get the current app context.

    Returns
    -------
    Any
        The current application instance.

    Raises
    ------
    RuntimeError
        If no app context is available.
    """
    app = _current_app.get()
    if app is None:
        raise RuntimeError("No app context available")
    return app
