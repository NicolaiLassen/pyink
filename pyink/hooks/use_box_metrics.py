"""useBoxMetrics hook — measure Box dimensions and position.

Port of Ink's ``src/hooks/use-box-metrics.ts``.
"""
from __future__ import annotations

from dataclasses import dataclass

from pyink.dom import DOMElement, add_layout_listener
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


def _find_root_node(node: DOMElement | None) -> DOMElement | None:
    """Walk up the parent chain to find the ink-root node."""
    while node is not None:
        if node.node_name == "ink-root":
            return node
        node = node.parent
    return None


def use_box_metrics(ref: Ref) -> BoxMetrics:
    """Measure a Box component's dimensions and position.

    Port of Ink's useBoxMetrics (use-box-metrics.ts lines 85–141).
    Runs measurement after every render and subscribes to layout
    listeners for sibling-driven updates.

    Parameters
    ----------
    ref : Ref
        A ref attached to the Box component to measure.

    Returns
    -------
    BoxMetrics
        The measured dimensions, position, and whether measurement has
        occurred.
    """
    width, set_width = use_state(0)
    height, set_height = use_state(0)
    left, set_left = use_state(0)
    top, set_top = use_state(0)
    has_measured, set_has_measured = use_state(False)

    # Capture app during render (NOT in effect)
    app = get_current_app()

    def measure() -> None:
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

    # Port of use-box-metrics.ts line 108: run after EVERY render (no deps)
    def effect():
        measure()

        # Port of use-box-metrics.ts lines 112–119: layout listener
        cleanups = []
        node = ref.current
        if isinstance(node, DOMElement):
            root = _find_root_node(node)
            if root is not None:
                unsub = add_layout_listener(root, measure)
                cleanups.append(unsub)

        # Port of use-box-metrics.ts lines 126–131: resize listener
        remove_resize = app.terminal.on_resize(measure)
        cleanups.append(remove_resize)

        def cleanup():
            for fn in cleanups:
                fn()

        return cleanup

    # No deps = run after every render (matching Ink line 108)
    use_effect(effect)

    return BoxMetrics(
        width=width,
        height=height,
        left=left,
        top=top,
        has_measured=has_measured,
    )
