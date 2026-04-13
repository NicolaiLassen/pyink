from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.fiber import Ref
from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_state import use_state


@dataclass
class BoxMetrics:
    """Measured box dimensions, matching Ink's BoxMetrics."""

    width: int
    height: int
    left: int
    top: int
    has_measured: bool


def use_box_metrics(ref: Ref) -> BoxMetrics:
    """Measure a Box component's dimensions and position.

    Matches Ink's useBoxMetrics hook.
    """
    width, set_width = use_state(0)
    height, set_height = use_state(0)
    left, set_left = use_state(0)
    top, set_top = use_state(0)
    has_measured, set_has_measured = use_state(False)

    # Capture app during render (NOT in effect)
    app = get_current_app()

    def effect():
        def measure():
            node = ref.current
            if node is None:
                return
            yn = getattr(node, "yoga_node", None)
            if yn is None:
                return

            set_width(int(yn.get_computed_width()))
            set_height(int(yn.get_computed_height()))
            set_left(int(yn.get_computed_left()))
            set_top(int(yn.get_computed_top()))
            set_has_measured(True)

        measure()

        remove = app.terminal.on_resize(measure)
        return remove

    use_effect(effect, ())

    return BoxMetrics(
        width=width,
        height=height,
        left=left,
        top=top,
        has_measured=has_measured,
    )
