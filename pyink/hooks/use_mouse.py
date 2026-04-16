"""useMouse hook — enable terminal mouse tracking.

When active, enables SGR mouse tracking so scroll wheel events
(``key.scroll_up`` / ``key.scroll_down``) are delivered to
``use_input`` handlers.
"""
from __future__ import annotations

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect


def use_mouse(*, active: bool = True) -> None:
    """Enable mouse tracking for scroll wheel events.

    Scroll events arrive via ``use_input`` as ``key.scroll_up``
    and ``key.scroll_down``. Other mouse events (click, drag) are
    consumed but not dispatched.

    Parameters
    ----------
    active : bool, optional
        Whether mouse tracking is enabled (default ``True``).
    """
    app = get_current_app()

    def effect():
        if not active:
            return None
        app.input_manager.enable_mouse_tracking()

        def cleanup():
            app.input_manager.disable_mouse_tracking()

        return cleanup

    use_effect(effect, (active,))
