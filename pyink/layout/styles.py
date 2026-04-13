"""Style application matching Ink's styles.ts 1:1.

Applies style props to yoga nodes using the same logic as Ink's
applyPositionStyles, applyMarginStyles, applyPaddingStyles,
applyFlexStyles, applyDimensionStyles, applyDisplayStyles,
applyBorderStyles, and applyGapStyles.
"""
from __future__ import annotations

from typing import Any

import pyyoga as yoga

# Style props that are NOT yoga layout props (visual-only)
NON_YOGA_PROPS = {
    # Text styling
    "color", "background_color", "bg_color", "background",
    "bold", "dim", "dim_color", "italic", "underline", "strikethrough",
    "inverse", "overline", "wrap", "text_wrap",
    # Border visual
    "border_style", "border_color",
    "border_top_color", "border_bottom_color", "border_left_color", "border_right_color",
    "border_background_color",
    "border_top_background_color", "border_bottom_background_color",
    "border_left_background_color", "border_right_background_color",
    "border_dim_color",
    "border_top_dim_color", "border_bottom_dim_color",
    "border_left_dim_color", "border_right_dim_color",
    # Border visibility (handled in border rendering, not yoga)
    "border_top", "border_bottom", "border_left", "border_right",
    # Overflow (handled in rendering)
    "overflow", "overflow_x", "overflow_y",
    # Transform
    "transform", "_static",
    # Background
    "background_color",
}


def apply_styles(node: Any, style: dict[str, Any]) -> None:
    """Apply all style props to a yoga Node, matching Ink's styles() function."""
    if node is None:
        return
    _apply_position_styles(node, style)
    _apply_margin_styles(node, style)
    _apply_padding_styles(node, style)
    _apply_flex_styles(node, style)
    _apply_dimension_styles(node, style)
    _apply_display_styles(node, style)
    _apply_border_styles(node, style)
    _apply_gap_styles(node, style)


def _apply_position_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyPositionStyles."""
    if "position" in style:
        pos = style["position"]
        if pos == "absolute":
            yn.position_type = yoga.PositionType.Absolute
        elif pos == "static":
            yn.position_type = yoga.PositionType.Static
        else:
            yn.position_type = yoga.PositionType.Relative

    for prop, edge in [
        ("top", yoga.Edge.Top),
        ("right", yoga.Edge.Right),
        ("bottom", yoga.Edge.Bottom),
        ("left", yoga.Edge.Left),
    ]:
        if prop not in style:
            continue
        val = style[prop]
        if isinstance(val, str) and val.endswith("%"):
            yn.set_position(edge, float(val.rstrip("%")))  # percent
        elif val is not None:
            yn.set_position(edge, val)


def _apply_margin_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyMarginStyles."""
    if "margin" in style:
        yn.set_margin(yoga.Edge.All, style["margin"] or 0)
    if "margin_x" in style:
        yn.set_margin(yoga.Edge.Horizontal, style["margin_x"] or 0)
    if "margin_y" in style:
        yn.set_margin(yoga.Edge.Vertical, style["margin_y"] or 0)
    if "margin_left" in style:
        yn.set_margin(yoga.Edge.Start, style["margin_left"] or 0)
    if "margin_right" in style:
        yn.set_margin(yoga.Edge.End, style["margin_right"] or 0)
    if "margin_top" in style:
        yn.set_margin(yoga.Edge.Top, style["margin_top"] or 0)
    if "margin_bottom" in style:
        yn.set_margin(yoga.Edge.Bottom, style["margin_bottom"] or 0)


def _apply_padding_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyPaddingStyles."""
    if "padding" in style:
        yn.set_padding(yoga.Edge.All, style["padding"] or 0)
    if "padding_x" in style:
        yn.set_padding(yoga.Edge.Horizontal, style["padding_x"] or 0)
    if "padding_y" in style:
        yn.set_padding(yoga.Edge.Vertical, style["padding_y"] or 0)
    if "padding_left" in style:
        yn.set_padding(yoga.Edge.Left, style["padding_left"] or 0)
    if "padding_right" in style:
        yn.set_padding(yoga.Edge.Right, style["padding_right"] or 0)
    if "padding_top" in style:
        yn.set_padding(yoga.Edge.Top, style["padding_top"] or 0)
    if "padding_bottom" in style:
        yn.set_padding(yoga.Edge.Bottom, style["padding_bottom"] or 0)


def _apply_flex_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyFlexStyles."""
    if "flex_grow" in style:
        yn.flex_grow = float(style["flex_grow"] or 0)
    if "flex_shrink" in style:
        val = style["flex_shrink"]
        yn.flex_shrink = float(val) if isinstance(val, (int, float)) else 1.0
    if "flex_wrap" in style:
        wrap_map = {
            "nowrap": yoga.Wrap.NoWrap, "no-wrap": yoga.Wrap.NoWrap,
            "wrap": yoga.Wrap.Wrap,
            "wrap-reverse": yoga.Wrap.WrapReverse, "wrap_reverse": yoga.Wrap.WrapReverse,
        }
        yn.flex_wrap = wrap_map.get(style["flex_wrap"], yoga.Wrap.NoWrap)
    if "flex_direction" in style:
        fd_map = {
            "row": yoga.FlexDirection.Row,
            "row-reverse": yoga.FlexDirection.RowReverse,
            "row_reverse": yoga.FlexDirection.RowReverse,
            "column": yoga.FlexDirection.Column,
            "column-reverse": yoga.FlexDirection.ColumnReverse,
            "column_reverse": yoga.FlexDirection.ColumnReverse,
        }
        yn.flex_direction = fd_map.get(style["flex_direction"], yoga.FlexDirection.Column)
    if "flex_basis" in style:
        val = style["flex_basis"]
        if isinstance(val, (int, float)):
            yn.flex_basis = val
        elif isinstance(val, str):
            yn.flex_basis = int(val.rstrip("%"))
    if "align_items" in style:
        ai_map = {
            "stretch": yoga.Align.Stretch,
            "flex-start": yoga.Align.FlexStart, "flex_start": yoga.Align.FlexStart,
            "center": yoga.Align.Center,
            "flex-end": yoga.Align.FlexEnd, "flex_end": yoga.Align.FlexEnd,
            "baseline": yoga.Align.Baseline,
        }
        yn.align_items = ai_map.get(style["align_items"], yoga.Align.Stretch)
    if "align_self" in style:
        as_map = {
            "auto": yoga.Align.Auto,
            "flex-start": yoga.Align.FlexStart, "flex_start": yoga.Align.FlexStart,
            "center": yoga.Align.Center,
            "flex-end": yoga.Align.FlexEnd, "flex_end": yoga.Align.FlexEnd,
            "stretch": yoga.Align.Stretch,
            "baseline": yoga.Align.Baseline,
        }
        yn.align_self = as_map.get(style["align_self"], yoga.Align.Auto)
    if "align_content" in style:
        ac_map = {
            "flex-start": yoga.Align.FlexStart, "flex_start": yoga.Align.FlexStart,
            "center": yoga.Align.Center,
            "flex-end": yoga.Align.FlexEnd, "flex_end": yoga.Align.FlexEnd,
            "stretch": yoga.Align.Stretch,
            "space-between": yoga.Align.SpaceBetween, "space_between": yoga.Align.SpaceBetween,
            "space-around": yoga.Align.SpaceAround, "space_around": yoga.Align.SpaceAround,
            "space-evenly": yoga.Align.SpaceEvenly, "space_evenly": yoga.Align.SpaceEvenly,
        }
        yn.align_content = ac_map.get(style["align_content"], yoga.Align.FlexStart)
    if "justify_content" in style:
        jc_map = {
            "flex-start": yoga.Justify.FlexStart, "flex_start": yoga.Justify.FlexStart,
            "center": yoga.Justify.Center,
            "flex-end": yoga.Justify.FlexEnd, "flex_end": yoga.Justify.FlexEnd,
            "space-between": yoga.Justify.SpaceBetween, "space_between": yoga.Justify.SpaceBetween,
            "space-around": yoga.Justify.SpaceAround, "space_around": yoga.Justify.SpaceAround,
            "space-evenly": yoga.Justify.SpaceEvenly, "space_evenly": yoga.Justify.SpaceEvenly,
        }
        yn.justify_content = jc_map.get(style["justify_content"], yoga.Justify.FlexStart)


def _apply_dimension_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyDimensionStyles."""
    for prop in ("width", "height", "min_width", "min_height", "max_width", "max_height"):
        if prop not in style:
            continue
        val = style[prop]
        if isinstance(val, str) and val.endswith("%"):
            setattr(yn, prop, int(val.rstrip("%")))
        elif isinstance(val, (int, float)):
            setattr(yn, prop, val)

    if "aspect_ratio" in style:
        yn.aspect_ratio = float(style["aspect_ratio"])


def _apply_display_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyDisplayStyles."""
    if "display" in style:
        yn.display = yoga.Display.Flex if style["display"] == "flex" else yoga.Display.None_


def _apply_border_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyBorderStyles.

    Border width in yoga is 1 if borderStyle is set (unless that edge is hidden).
    """
    has_changes = any(
        k in style
        for k in ("border_style", "border_top", "border_bottom", "border_left", "border_right")
    )
    if not has_changes:
        return

    bw = 1 if style.get("border_style") else 0

    yn.set_border(yoga.Edge.Top, 0 if style.get("border_top") is False else bw)
    yn.set_border(yoga.Edge.Bottom, 0 if style.get("border_bottom") is False else bw)
    yn.set_border(yoga.Edge.Left, 0 if style.get("border_left") is False else bw)
    yn.set_border(yoga.Edge.Right, 0 if style.get("border_right") is False else bw)


def _apply_gap_styles(yn: Any, style: dict) -> None:
    """Match Ink's applyGapStyles."""
    if "gap" in style:
        yn.set_gap(yoga.Gutter.All, style["gap"] or 0)
    if "column_gap" in style:
        yn.set_gap(yoga.Gutter.Column, style["column_gap"] or 0)
    if "row_gap" in style:
        yn.set_gap(yoga.Gutter.Row, style["row_gap"] or 0)
