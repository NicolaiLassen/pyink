from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_ref import use_ref
from pyink.hooks.use_state import use_state


@dataclass
class AnimationResult:
    """Return type of use_animation, matching Ink's AnimationResult."""

    frame: int
    time: float  # total elapsed ms
    delta: float  # ms since previous tick
    reset: Callable[[], None]


def use_animation(
    *, interval: int = 100, is_active: bool = True
) -> AnimationResult:
    """Frame-based animation hook, matching Ink's useAnimation.

    Returns frame count, elapsed time, delta, and a reset function.
    """
    frame, set_frame = use_state(0)
    elapsed_time, set_elapsed_time = use_state(0.0)
    delta, set_delta = use_state(0.0)
    start_time_ref = use_ref(0.0)
    last_time_ref = use_ref(0.0)

    # Capture app during render (NOT in effect - context is cleared after render)
    app = get_current_app()

    def reset() -> None:
        set_frame(0)
        set_elapsed_time(0.0)
        set_delta(0.0)
        start_time_ref.current = time.monotonic() * 1000
        last_time_ref.current = time.monotonic() * 1000

    def effect():
        if not is_active:
            return None

        now = time.monotonic() * 1000
        start_time_ref.current = now
        last_time_ref.current = now

        def tick() -> None:
            current = time.monotonic() * 1000
            dt = current - last_time_ref.current
            last_time_ref.current = current
            total = current - start_time_ref.current

            set_frame(lambda f: f + 1)
            set_elapsed_time(total)
            set_delta(dt)

        actual_interval = max(1, min(interval, 2_147_483_647))
        handle = app.add_timer(actual_interval / 1000.0, tick, repeating=True)

        def cleanup():
            app.remove_timer(handle)

        return cleanup

    use_effect(effect, (is_active, interval))

    return AnimationResult(
        frame=frame,
        time=elapsed_time,
        delta=delta,
        reset=reset,
    )
