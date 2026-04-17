"""ProgressBar component — filled horizontal bar.

Port of ink-progress-bar (https://github.com/brigand/ink-progress-bar).
"""
from __future__ import annotations

from pyink.component import component
from pyink.vnode import Box, Text


@component
def ProgressBar(
    percent: float = 0,
    width: int | None = None,
    character: str = "\u2588",  # █
    empty_character: str = " ",
    color: str | None = None,
    background_color: str | None = None,
    rightPad: str = "",
):
    """Horizontal filled progress bar.

    Parameters
    ----------
    percent : float
        Fill percentage in [0.0, 1.0] or [0, 100].
    width : int or None
        Total width in cols. If None, fills available space.
    character : str
        Filled-bar character.
    empty_character : str
        Empty-bar character (shown for the remaining portion).
    color : str, optional
        Color of the filled bar.
    background_color : str, optional
        Color of the empty portion.
    rightPad : str
        Character(s) appended after the bar (e.g. ``" "`` for spacing).
    """
    # Clamp percent to [0, 1]. Matches ink-progress-bar.
    percent = max(0.0, min(1.0, percent))

    w = width if width is not None else 20

    filled_count = int(w * percent)
    empty_count = w - filled_count

    filled = character * filled_count
    empty = empty_character * empty_count

    parts = []
    if filled:
        parts.append(Text(filled, color=color))
    if empty:
        parts.append(Text(empty, color=background_color or color, dim=True))
    if rightPad:
        parts.append(Text(rightPad))

    return Box(*parts, flex_direction="row", width=width)
