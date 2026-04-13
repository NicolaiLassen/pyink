from __future__ import annotations

from typing import Callable

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_ref import use_ref


def use_paste(
    handler: Callable[[str], None], *, is_active: bool = True
) -> None:
    """Subscribe to paste events. Matches Ink's usePaste hook.

    Automatically enables bracketed paste mode while active.
    Pasted text arrives as a single string.
    """
    handler_ref = use_ref(handler)
    handler_ref.current = handler

    def effect():
        if not is_active:
            return None

        app = get_current_app()

        def on_paste(text: str) -> None:
            handler_ref.current(text)

        app.input_manager.add_paste_listener(on_paste)
        app.input_manager.enable_bracketed_paste()

        def cleanup():
            app.input_manager.remove_paste_listener(on_paste)
            app.input_manager.disable_bracketed_paste()

        return cleanup

    use_effect(effect, (is_active,))
