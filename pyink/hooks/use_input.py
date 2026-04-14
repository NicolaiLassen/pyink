from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_ref import use_ref

if TYPE_CHECKING:
    from pyink.input.keys import Key


def use_input(
    handler: Callable[[str, Key], None], *, active: bool = True
) -> None:
    """Subscribe to keyboard input.

    handler(input_str, key) is called for each keypress while active is True.

    Parameters
    ----------
    handler : Callable[[str, Key], None]
        Callback invoked with ``(input_str, key)`` on each keypress.
    active : bool, optional
        Whether the input listener is active. When ``False``, the handler
        is not subscribed.
    """
    app = get_current_app()
    handler_ref = use_ref(handler)
    handler_ref.current = handler  # always point to latest closure

    def effect():
        if not active:
            return None

        def on_input(input_str: str, key: Key) -> None:
            handler_ref.current(input_str, key)

        app.input_manager.add_listener(on_input)

        def cleanup():
            app.input_manager.remove_listener(on_input)

        return cleanup

    use_effect(effect, (active,))
