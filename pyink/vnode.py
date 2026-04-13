"""VNode types and element factory functions matching Ink's component API.

All Ink components are represented here: Box, Text, Static, Transform,
Spacer, Newline.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VNode:
    """A virtual DOM node - the output of component render functions."""

    type: str | Callable
    props: dict[str, Any] = field(default_factory=dict)
    children: list[VNode | str] = field(default_factory=list)
    key: str | int | None = None


def _make_element(node_type: str, *children: VNode | str, **props: Any) -> VNode:
    key = props.pop("key", None)
    return VNode(type=node_type, props=props, children=list(children), key=key)


def Box(*children: VNode | str, **props: Any) -> VNode:
    """Layout container with flexbox styling. Matches Ink's <Box>.

    Supports all flexbox props: flex_direction, justify_content, align_items,
    padding, margin, width, height, border_style, overflow, etc.
    """
    return _make_element("ink-box", *children, **props)


def Text(*children: VNode | str, **props: Any) -> VNode:
    """Text display with styling. Matches Ink's <Text>.

    Supports: color, background_color, bold, dim, dim_color, italic,
    underline, strikethrough, inverse, overline, text_wrap.
    """
    return _make_element("ink-text", *children, **props)


def Spacer(**props: Any) -> VNode:
    """Flexible space that expands along the major axis. Matches Ink's <Spacer>."""
    props.setdefault("flex_grow", 1)
    return _make_element("ink-box", **props)


def Newline(count: int = 1) -> VNode:
    """Adds newline character(s). Matches Ink's <Newline>."""
    return _make_element("ink-text", "\n" * count)


def Static(
    *children: VNode | str,
    items: list | None = None,
    render_item: Callable | None = None,
    **props: Any,
) -> VNode:
    """Render permanent output that doesn't re-render. Matches Ink's <Static>.

    Can use items + render_item pattern (like Ink) or direct children.
    """
    props["_static"] = True
    if items is not None and render_item is not None:
        rendered_children = [render_item(item, i) for i, item in enumerate(items)]
        return _make_element("ink-box", *rendered_children, **props)
    return _make_element("ink-box", *children, **props)


def Transform(
    *children: VNode | str,
    transform: Callable[[str, int], str] | None = None,
    **props: Any,
) -> VNode:
    """Apply transformations to string output. Matches Ink's <Transform>.

    The transform function receives (line: str, index: int) and returns
    the transformed string, applied per-line.
    """
    props["_transform"] = transform
    return _make_element("ink-box", *children, **props)
