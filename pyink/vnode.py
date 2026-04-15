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

    Port of Box.tsx lines 83–91. Applies default styles:
    ``flex_wrap='nowrap'``, ``flex_direction='row'``, ``flex_grow=0``,
    ``flex_shrink=1``, and overflow defaults.

    Parameters
    ----------
    *children : VNode | str
        Child elements or text content.
    **props : Any
        Flexbox style and layout properties. Supports all yoga props:
        ``flex_direction``, ``justify_content``, ``align_items``,
        ``padding``, ``margin``, ``width``, ``height``, ``border_style``,
        ``overflow``, etc.

    Returns
    -------
    VNode
        A virtual node representing the box element.
    """
    # Port of Box.tsx lines 83–91: apply defaults before user props
    props.setdefault("flex_wrap", "nowrap")
    props.setdefault("flex_direction", "row")
    props.setdefault("flex_grow", 0)
    props.setdefault("flex_shrink", 1)

    # Port of Box.tsx lines 90–91: overflow defaults
    overflow = props.get("overflow")
    if "overflow_x" not in props:
        props["overflow_x"] = props.get("overflow_x", overflow or "visible")
    if "overflow_y" not in props:
        props["overflow_y"] = props.get("overflow_y", overflow or "visible")

    return _make_element("ink-box", *children, **props)


def Text(*children: VNode | str, **props: Any) -> VNode:
    """Text display with styling. Matches Ink's <Text>.

    Port of Text.tsx line 139. Applies default styles:
    ``flex_grow=0``, ``flex_shrink=1``, ``flex_direction='row'``,
    ``text_wrap='wrap'``.

    Supports: ``color``, ``background_color``, ``bold``, ``dim``,
    ``dim_color``, ``italic``, ``underline``, ``strikethrough``,
    ``inverse``, ``overline``, ``text_wrap``.

    Parameters
    ----------
    *children : VNode | str
        Child elements or text content.
    **props : Any
        Text style properties.

    Returns
    -------
    VNode
        A virtual node representing the text element.
    """
    # Port of Text.tsx line 139: default styles
    props.setdefault("flex_grow", 0)
    props.setdefault("flex_shrink", 1)
    props.setdefault("flex_direction", "row")
    # Port of Text.tsx line 80: wrap='wrap' default
    props.setdefault("text_wrap", "wrap")
    return _make_element("ink-text", *children, **props)


def Spacer(**props: Any) -> VNode:
    """Flexible space that expands along the major axis. Matches Ink's <Spacer>.

    Parameters
    ----------
    **props : Any
        Additional layout properties.

    Returns
    -------
    VNode
        A virtual node representing the spacer element.
    """
    props.setdefault("flex_grow", 1)
    return _make_element("ink-box", **props)


def Newline(count: int = 1) -> VNode:
    """Adds newline character(s). Matches Ink's <Newline>.

    Parameters
    ----------
    count : int, optional
        Number of newlines to insert (default ``1``).

    Returns
    -------
    VNode
        A virtual node containing the newline text.
    """
    return _make_element("ink-text", "\n" * count)


# ── Static component ──

# Cached component function — created lazily on first call so:
# 1. No circular import (pyink.component imports pyink.vnode)
# 2. The reconciler sees the SAME function identity on every render,
#    preserving fiber hook state (index for "only render new items")
_static_inner_fn: Callable | None = None


def _get_static_inner() -> Callable:
    """Lazily create and cache the ``_static_inner`` component.

    Returns
    -------
    Callable
        The cached component function.
    """
    global _static_inner_fn
    if _static_inner_fn is not None:
        return _static_inner_fn

    from pyink.component import component
    from pyink.hooks.use_effect import use_layout_effect
    from pyink.hooks.use_state import use_state

    @component
    def _static_inner(items, render_item, style):
        """Internal component for Static.

        Port of Ink's Static.tsx lines 28–58. Uses ``useLayoutEffect``
        to clear children after the first commit, so items are only
        written to terminal scrollback once.
        """
        index, set_index = use_state(0)

        # Only render items from index onward (new items).
        items_to_render = items[index:] if items else []

        def sync_index():
            set_index(len(items) if items else 0)

        # Port of Static.tsx lines 36–38: useLayoutEffect fires during
        # commit (before render output), clearing children so they're
        # only rendered to scrollback once.
        use_layout_effect(sync_index, (len(items) if items else 0,))

        rendered = []
        if render_item and items_to_render:
            rendered = [
                render_item(item, index + i)
                for i, item in enumerate(items_to_render)
            ]

        return _make_element(
            "ink-box",
            *rendered,
            internal_static=True,
            position="absolute",
            flex_direction="column",
            **style,
        )

    _static_inner_fn = _static_inner
    return _static_inner_fn


def Static(
    *children: VNode | str,
    items: list | None = None,
    render_item: Callable | None = None,
    **props: Any,
) -> VNode:
    """Render permanent output that doesn't re-render. Matches Ink's <Static>.

    Port of Ink's Static.tsx. Only renders NEW items since the last
    render. Previously rendered items are already in terminal scrollback.

    Parameters
    ----------
    *children : VNode | str
        Direct child elements or text content.
    items : list or None, optional
        List of data items to render.
    render_item : Callable or None, optional
        Function called as ``render_item(item, index)`` to produce a VNode
        for each item.
    **props : Any
        Additional style properties passed to the container.

    Returns
    -------
    VNode
        A virtual node representing the static container.
    """
    style = {k: v for k, v in props.items() if k not in ("items", "render_item")}

    if items is not None and render_item is not None:
        inner = _get_static_inner()
        return inner(items=items, render_item=render_item, style=style)

    # Direct children mode — no tracking needed, render all.
    props["internal_static"] = True
    props["position"] = "absolute"
    return _make_element("ink-box", *children, **props)


def Transform(
    *children: VNode | str,
    transform: Callable[[str, int], str] | None = None,
    **props: Any,
) -> VNode:
    """Apply transformations to string output. Matches Ink's <Transform>.

    Port of Transform.tsx. The transform function receives
    ``(line: str, index: int)`` and returns the transformed string,
    applied per-line.

    Parameters
    ----------
    *children : VNode | str
        Child elements or text content.
    transform : Callable[[str, int], str] or None, optional
        Per-line transformation function.
    **props : Any
        Additional properties.

    Returns
    -------
    VNode
        A virtual node representing the transform container.
    """
    props["internal_transform"] = transform
    # Port of Transform.tsx: flex_grow=0, flex_shrink=1, flex_direction=row
    props.setdefault("flex_grow", 0)
    props.setdefault("flex_shrink", 1)
    props.setdefault("flex_direction", "row")
    return _make_element("ink-text", *children, **props)
