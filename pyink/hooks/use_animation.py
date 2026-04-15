"""useAnimation hook — frame-based animation.

Port of Ink's ``src/hooks/use-animation.ts``.
Uses the shared animation scheduler from the App for efficiency.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_layout_effect
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
    """Frame-based animation hook using the shared App scheduler.

    Port of Ink's useAnimation (use-animation.ts lines 67–143).
    All animations share a single timer in the App for efficiency.

    Parameters
    ----------
    interval : int, optional
        Tick interval in milliseconds. Clamped to valid range.
    is_active : bool, optional
        Whether the animation timer is running.

    Returns
    -------
    AnimationResult
        An object containing ``frame``, ``time``, ``delta``, and ``reset``.
    """
    frame, set_frame = use_state(0)
    elapsed_time, set_elapsed_time = use_state(0.0)
    delta, set_delta = use_state(0.0)
    start_time_ref = use_ref(0.0)
    last_time_ref = use_ref(0.0)

    # Capture app during render (NOT in effect - context is cleared after render)
    app = get_current_app()

    def reset() -> None:
        import time

        now = time.monotonic() * 1000
        set_frame(0)
        set_elapsed_time(0.0)
        set_delta(0.0)
        start_time_ref.current = now
        last_time_ref.current = now

    def effect():
        if not is_active:
            return None

        actual_interval = max(1, min(interval, 2_147_483_647))

        def tick(current_time: float) -> None:
            dt = current_time - last_time_ref.current
            last_time_ref.current = current_time
            total = current_time - start_time_ref.current

            set_frame(lambda f: f + 1)
            set_elapsed_time(total)
            set_delta(dt)

        # Use shared animation scheduler if available (port of App.tsx subscribe)
        if hasattr(app, "subscribe_animation"):
            start_time, unsubscribe = app.subscribe_animation(
                tick, actual_interval
            )
            start_time_ref.current = start_time
            last_time_ref.current = start_time
            return unsubscribe

        # Fallback: per-hook timer (for render_to_string_sync etc.)
        import time

        now = time.monotonic() * 1000
        start_time_ref.current = now
        last_time_ref.current = now

        def simple_tick() -> None:
            tick(time.monotonic() * 1000)

        handle = app.add_timer(
            actual_interval / 1000.0, simple_tick, repeating=True
        )
        return lambda: app.remove_timer(handle)

    # Port of Ink's use-animation.ts: useLayoutEffect for synchronous
    # subscription during commit, matching React's timing semantics.
    use_layout_effect(effect, (is_active, interval))

    return AnimationResult(
        frame=frame,
        time=elapsed_time,
        delta=delta,
        reset=reset,
    )
