from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pyink.hooks.context import get_current_fiber, get_schedule_update

T = TypeVar("T")


def use_state(initial: T) -> tuple[T, Callable[[T | Callable[[T], T]], None]]:
    """React-like state hook.

    Returns (current_value, set_state). set_state accepts either a new value
    or a function that receives the previous value and returns the new value.

    Parameters
    ----------
    initial : T
        The initial state value, used on the first render only.

    Returns
    -------
    tuple[T, Callable[[T | Callable[[T], T]], None]]
        A tuple of (current_value, set_state). set_state triggers a re-render
        when the new value differs from the current value.
    """
    fiber = get_current_fiber()
    idx = fiber.hook_index
    fiber.hook_index += 1

    # First render: initialize
    if idx >= len(fiber.hook_state):
        fiber.hook_state.append(initial)

    current_value = fiber.hook_state[idx]

    # Capture schedule function NOW (during render), not at call time.
    # When set_state is called from input handlers or effects, the
    # _schedule_update ContextVar is no longer set.
    schedule = get_schedule_update()

    def set_state(new_value: T | Callable[[T], T]) -> None:
        if callable(new_value):
            new_value = new_value(fiber.hook_state[idx])
        if new_value is not fiber.hook_state[idx]:
            fiber.hook_state[idx] = new_value
            schedule(fiber)

    return current_value, set_state
