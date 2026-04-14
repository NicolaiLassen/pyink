from __future__ import annotations

from dataclasses import dataclass

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_state import use_state
from pyink.terminal import get_terminal_size


@dataclass
class WindowSize:
    """Terminal window dimensions, matching Ink's WindowSize."""

    columns: int
    rows: int


def use_window_size() -> WindowSize:
    """Get terminal window dimensions. Re-renders on resize.

    Matches Ink's useWindowSize hook.

    Returns
    -------
    WindowSize
        The current terminal dimensions with ``columns`` and ``rows``.
    """
    cols, rows = get_terminal_size()
    columns, set_columns = use_state(cols)
    row_count, set_rows = use_state(rows)

    # Capture app during render (NOT in effect)
    app = get_current_app()

    def effect():
        def on_resize():
            c, r = get_terminal_size()
            set_columns(c)
            set_rows(r)

        remove = app.terminal.on_resize(on_resize)
        return remove

    use_effect(effect, ())

    return WindowSize(columns=columns, rows=row_count)
