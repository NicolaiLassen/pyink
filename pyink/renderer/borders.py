"""Border rendering matching Ink's render-border.ts 1:1.

Key: Ink writes side borders as multi-line strings (char + '\\n' repeated),
not as individual writes per row. This matches how Output processes writes.
"""
from __future__ import annotations

from typing import Any

from pyink.renderer.ansi import style_text

# Border character sets matching Ink's cli-boxes
BORDER_STYLES: dict[str, dict[str, str]] = {
    "single": {
        "topLeft": "\u250c", "top": "\u2500", "topRight": "\u2510",
        "left": "\u2502", "right": "\u2502",
        "bottomLeft": "\u2514", "bottom": "\u2500", "bottomRight": "\u2518",
    },
    "double": {
        "topLeft": "\u2554", "top": "\u2550", "topRight": "\u2557",
        "left": "\u2551", "right": "\u2551",
        "bottomLeft": "\u255a", "bottom": "\u2550", "bottomRight": "\u255d",
    },
    "round": {
        "topLeft": "\u256d", "top": "\u2500", "topRight": "\u256e",
        "left": "\u2502", "right": "\u2502",
        "bottomLeft": "\u2570", "bottom": "\u2500", "bottomRight": "\u256f",
    },
    "bold": {
        "topLeft": "\u250f", "top": "\u2501", "topRight": "\u2513",
        "left": "\u2503", "right": "\u2503",
        "bottomLeft": "\u2517", "bottom": "\u2501", "bottomRight": "\u251b",
    },
    "single-double": {
        "topLeft": "\u2553", "top": "\u2500", "topRight": "\u2556",
        "left": "\u2551", "right": "\u2551",
        "bottomLeft": "\u2559", "bottom": "\u2500", "bottomRight": "\u255c",
    },
    "double-single": {
        "topLeft": "\u2552", "top": "\u2550", "topRight": "\u2555",
        "left": "\u2502", "right": "\u2502",
        "bottomLeft": "\u2558", "bottom": "\u2550", "bottomRight": "\u255b",
    },
    "classic": {
        "topLeft": "+", "top": "-", "topRight": "+",
        "left": "|", "right": "|",
        "bottomLeft": "+", "bottom": "-", "bottomRight": "+",
    },
    "arrow": {
        "topLeft": "\u2191", "top": "\u2192", "topRight": "\u2193",
        "left": "\u2191", "right": "\u2193",
        "bottomLeft": "\u2191", "bottom": "\u2190", "bottomRight": "\u2193",
    },
}


def _style_piece(
    text: str,
    color: str | None,
    bg_color: str | None,
    is_dim: bool,
) -> str:
    """Apply color, background, dim to a border piece. Matches Ink's stylePiece."""
    kwargs: dict[str, Any] = {}
    if color:
        kwargs["color"] = color
    if bg_color:
        kwargs["background_color"] = bg_color
    if is_dim:
        kwargs["dim"] = True
    return style_text(text, **kwargs) if kwargs else text


def render_border(
    x: int,
    y: int,
    node_style: dict[str, Any],
    yoga_width: int,
    yoga_height: int,
    output: Any,
) -> None:
    """Render border matching Ink's renderBorder() exactly.

    Writes borders as multi-line strings like Ink does.

    Parameters
    ----------
    x : int
        Left coordinate of the border box.
    y : int
        Top coordinate of the border box.
    node_style : dict[str, Any]
        Style dictionary containing border configuration (``border_style``,
        per-edge visibility, colors, dim flags, etc.).
    yoga_width : int
        Total width of the node (including border).
    yoga_height : int
        Total height of the node (including border).
    output : Any
        The ``Output`` buffer to write border characters into.
    """
    border_style = node_style.get("border_style")
    if not border_style or border_style == "none":
        return

    width = yoga_width
    height = yoga_height

    if width < 2 or height < 2:
        return

    box = BORDER_STYLES.get(border_style, BORDER_STYLES["single"])

    # Per-edge colors with fallback (matching Ink exactly)
    fallback_color = node_style.get("border_color")
    top_color = node_style.get("border_top_color", fallback_color)
    bottom_color = node_style.get("border_bottom_color", fallback_color)
    left_color = node_style.get("border_left_color", fallback_color)
    right_color = node_style.get("border_right_color", fallback_color)

    fallback_bg = node_style.get("border_background_color")
    top_bg = node_style.get("border_top_background_color", fallback_bg)
    bottom_bg = node_style.get("border_bottom_background_color", fallback_bg)
    left_bg = node_style.get("border_left_background_color", fallback_bg)
    right_bg = node_style.get("border_right_background_color", fallback_bg)

    fallback_dim = node_style.get("border_dim_color", False)
    top_dim = node_style.get("border_top_dim_color", fallback_dim)
    bottom_dim = node_style.get("border_bottom_dim_color", fallback_dim)
    left_dim = node_style.get("border_left_dim_color", fallback_dim)
    right_dim = node_style.get("border_right_dim_color", fallback_dim)

    show_top = node_style.get("border_top", True) is not False
    show_bottom = node_style.get("border_bottom", True) is not False
    show_left = node_style.get("border_left", True) is not False
    show_right = node_style.get("border_right", True) is not False

    content_width = width - (1 if show_left else 0) - (1 if show_right else 0)

    # Top border (single line)
    if show_top:
        top_border = (
            (box["topLeft"] if show_left else "")
            + box["top"] * content_width
            + (box["topRight"] if show_right else "")
        )
        top_border = _style_piece(top_border, top_color, top_bg, top_dim)
        output.write(x, y, top_border)

    # Vertical border height
    vertical_height = height
    if show_top:
        vertical_height -= 1
    if show_bottom:
        vertical_height -= 1

    offset_y = 1 if show_top else 0

    # Left border - multi-line string like Ink: (char + '\n').repeat(height)
    if show_left:
        one = _style_piece(box["left"], left_color, left_bg, left_dim)
        left_border = (one + "\n") * vertical_height
        output.write(x, y + offset_y, left_border)

    # Right border - multi-line string like Ink
    if show_right:
        one = _style_piece(box["right"], right_color, right_bg, right_dim)
        right_border = (one + "\n") * vertical_height
        output.write(x + width - 1, y + offset_y, right_border)

    # Bottom border (single line)
    if show_bottom:
        bottom_border = (
            (box["bottomLeft"] if show_left else "")
            + box["bottom"] * content_width
            + (box["bottomRight"] if show_right else "")
        )
        bottom_border = _style_piece(bottom_border, bottom_color, bottom_bg, bottom_dim)
        output.write(x, y + height - 1, bottom_border)
