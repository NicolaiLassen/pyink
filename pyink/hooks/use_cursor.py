from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyink.hooks.context import get_current_app


@dataclass
class CursorPosition:
    """Cursor position relative to Ink output origin."""

    x: int
    y: int


def use_cursor() -> dict[str, Callable]:
    """Control terminal cursor position. Matches Ink's useCursor hook.

    Returns dict with set_cursor_position(pos) where pos is CursorPosition or None.
    Pass None to hide cursor.
    """
    app = get_current_app()

    def set_cursor_position(position: CursorPosition | None) -> None:
        app.set_cursor_position(position)

    return {"set_cursor_position": set_cursor_position}
