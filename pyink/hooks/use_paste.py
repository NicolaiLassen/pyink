"""usePaste hook — subscribe to paste events.

Port of Ink's ``src/hooks/use-paste.ts``.
"""
from __future__ import annotations

from collections.abc import Callable

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_ref import use_ref


def use_paste(
    handler: Callable[[str], None], *, is_active: bool = True
) -> None:
    """Subscribe to paste events.

    Port of Ink's usePaste (use-paste.ts lines 39–81).
    Enables raw mode AND bracketed paste mode while active.

    Parameters
    ----------
    handler : Callable[[str], None]
        Callback invoked with the pasted text string.
    is_active : bool, optional
        Whether paste listening is active.
    """
    handler_ref = use_ref(handler)
    handler_ref.current = handler

    # Capture app during render (context cleared after render)
    app = get_current_app()

    def effect():
        if not is_active:
            return None

        def on_paste(text: str) -> None:
            handler_ref.current(text)

        # Port of use-paste.ts lines 52–53: enable BOTH raw mode and bracketed paste
        app.input_manager.enable_raw_mode()
        app.input_manager.enable_bracketed_paste()
        app.input_manager.add_paste_listener(on_paste)

        def cleanup():
            app.input_manager.remove_paste_listener(on_paste)
            app.input_manager.disable_bracketed_paste()
            app.input_manager.disable_raw_mode()

        return cleanup

    use_effect(effect, (is_active,))
