from __future__ import annotations

from typing import Any, TypeVar

from pyink.fiber import Ref
from pyink.hooks.context import get_current_fiber

T = TypeVar("T")


def use_ref(initial: T = None) -> Ref:
    """React-like ref hook. Returns a mutable Ref object stable across renders."""
    fiber = get_current_fiber()
    idx = fiber.hook_index
    fiber.hook_index += 1

    if idx >= len(fiber.hook_state):
        fiber.hook_state.append(Ref(current=initial))

    return fiber.hook_state[idx]


def use_memo(factory: Any, deps: tuple) -> Any:
    """React-like memo hook. Recomputes only when deps change."""
    fiber = get_current_fiber()
    idx = fiber.hook_index
    fiber.hook_index += 1

    if idx >= len(fiber.hook_state):
        fiber.hook_state.append((deps, factory()))
    else:
        prev_deps, prev_value = fiber.hook_state[idx]
        if deps != prev_deps:
            fiber.hook_state[idx] = (deps, factory())

    return fiber.hook_state[idx][1]


def use_callback(callback: Any, deps: tuple) -> Any:
    """React-like useCallback. Returns a stable callback reference when deps haven't changed."""
    return use_memo(lambda: callback, deps)
