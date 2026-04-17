"""Spinner component — animated loading indicator.

Port of ink-spinner (https://github.com/vadimdemedes/ink-spinner).
Uses a shared animation scheduler via ``use_animation``.
"""
from __future__ import annotations

from pyink.component import component
from pyink.hooks.use_animation import use_animation
from pyink.vnode import Text

# Preset frame sets (subset of cli-spinners)
SPINNERS: dict[str, dict] = {
    "dots": {
        "interval": 80,
        "frames": ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c",
                   "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"],
    },
    "line": {
        "interval": 130,
        "frames": ["-", "\\", "|", "/"],
    },
    "arc": {
        "interval": 100,
        "frames": ["\u25dc", "\u25e0", "\u25dd", "\u25de", "\u25e1", "\u25df"],
    },
    "arrow": {
        "interval": 100,
        "frames": ["\u2190", "\u2196", "\u2191", "\u2197", "\u2192",
                   "\u2198", "\u2193", "\u2199"],
    },
    "bouncing_bar": {
        "interval": 80,
        "frames": ["[    ]", "[=   ]", "[==  ]", "[=== ]", "[====]",
                   "[ ===]", "[  ==]", "[   =]", "[    ]", "[   =]",
                   "[  ==]", "[ ===]", "[====]", "[=== ]", "[==  ]",
                   "[=   ]"],
    },
    "dots2": {
        "interval": 80,
        "frames": ["\u28fe", "\u28fd", "\u28fb", "\u28bf", "\u287f",
                   "\u28df", "\u28ef", "\u28f7"],
    },
    "star": {
        "interval": 70,
        "frames": ["\u2736", "\u2737", "\u2738", "\u2739", "\u273a",
                   "\u2739", "\u2738", "\u2737"],
    },
}


@component
def Spinner(
    type: str = "dots",
    color: str | None = None,
):
    """Animated spinner.

    Parameters
    ----------
    type : str
        Preset name — ``"dots"``, ``"line"``, ``"arc"``, ``"arrow"``,
        ``"bouncing_bar"``, ``"dots2"``, ``"star"``.
    color : str, optional
        Color of the spinner character.
    """
    preset = SPINNERS.get(type, SPINNERS["dots"])
    interval = preset["interval"]
    frames = preset["frames"]

    anim = use_animation(interval=interval, is_active=True)
    frame_char = frames[anim.frame % len(frames)]

    return Text(frame_char, color=color)
