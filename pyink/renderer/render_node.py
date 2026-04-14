"""Render pipeline matching Ink's render-node-to-output.ts and renderer.ts 1:1.

Walks the DOM tree, applies yoga layout positions, renders borders,
backgrounds, text with wrapping/truncation, and overflow clipping.
"""
from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

import pyyoga as yoga

from pyink.dom import DOMElement, TextNode, squash_text_nodes
from pyink.layout.engine import _wrap_text, compute_layout, visible_width
from pyink.renderer.ansi import style_text
from pyink.renderer.borders import render_border
from pyink.renderer.output import Output


class RenderResult:
    """Port of Ink's renderer.ts Result type."""

    def __init__(self, output: str, output_height: int, static_output: str = "") -> None:
        self.output = output
        self.output_height = output_height
        self.static_output = static_output


def renderer(dom: DOMElement | None, width: int | None = None) -> RenderResult:
    """Render the DOM tree, separating static and dynamic output.

    Static nodes (marked with ``_static``) are rendered into a
    separate ``static_output`` string that the app writes once to
    stdout. Dynamic content is rendered into ``output`` which
    log-update redraws in place.

    Parameters
    ----------
    dom : DOMElement or None
        Root DOM element.
    width : int, optional
        Terminal width override.

    Returns
    -------
    RenderResult
        Contains ``output`` (dynamic), ``output_height``, and
        ``static_output`` (new static items to write once).
    """
    if dom is None or dom.yoga_node is None:
        return RenderResult("", 0)

    if width is None:
        try:
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 80

    compute_layout(dom, width, 500)

    yn = dom.yoga_node
    output_width = int(yn.get_computed_width())
    output_height = int(yn.get_computed_height())

    # Pass 1: render only static nodes.
    static_buf = Output(output_width, output_height)
    _render_node(dom, static_buf, 0, 0, transformers=[], skip_static=False, only_static=True)
    static_output = static_buf.get()

    # Pass 2: render only dynamic nodes (skip static).
    dynamic_buf = Output(output_width, output_height)
    _render_node(dom, dynamic_buf, 0, 0, transformers=[], skip_static=True)
    dynamic_output = dynamic_buf.get()

    # Dynamic output height = lines in dynamic output.
    dynamic_lines = dynamic_output.split("\n")
    dynamic_height = len(dynamic_lines)

    return RenderResult(
        output=dynamic_output,
        output_height=dynamic_height,
        static_output=static_output,
    )


def render_to_string(dom: DOMElement | None, width: int | None = None) -> str:
    """Convenience wrapper — returns just the output string."""
    return renderer(dom, width).output


def _render_node(
    node: DOMElement | TextNode,
    output: Output,
    offset_x: int,
    offset_y: int,
    *,
    transformers: list[Callable] | None = None,
    skip_static: bool = True,
    only_static: bool = False,
) -> None:
    """Recursively render a DOM node to the output buffer.

    Parameters
    ----------
    skip_static : bool
        Skip nodes marked ``_static`` (render dynamic only).
    only_static : bool
        Only render nodes inside ``_static`` subtrees.
    """
    if isinstance(node, TextNode):
        return

    yn = node.yoga_node
    if yn is None:
        return

    display = node.style.get("display")
    if display == "none":
        return

    is_static = node.style.get("_static")

    if skip_static and is_static:
        return

    if only_static and not is_static:
        # Not a static node — check if any children are static.
        # Only recurse into containers that might hold static children.
        if node.node_name in ("ink-root", "ink-box"):
            for child in node.children:
                _render_node(
                    child, output, offset_x, offset_y,
                    transformers=transformers,
                    skip_static=False,
                    only_static=True,
                )
        return

    # Left and top positions are relative to parent (matching Ink)
    x = offset_x + int(yn.layout_left)
    y = offset_y + int(yn.layout_top)
    w = int(yn.layout_width)
    h = int(yn.layout_height)

    # Transformers chain (matching Ink: prepend internal_transform)
    new_transformers = list(transformers or [])
    transform_fn = node.style.get("_transform")
    if callable(transform_fn):
        new_transformers = [transform_fn] + new_transformers

    if node.node_name == "ink-text":
        text = squash_text_nodes(node)

        if len(text) > 0:
            current_width = _widest_line(text)
            max_width = _get_max_width(yn)

            if current_width > max_width:
                text_wrap = node.style.get("text_wrap", "wrap")
                text = _wrap_text_with_mode(text, max_width, text_wrap)

            text = _apply_padding_to_text(node, text)

            # Collect text styles
            style_props = _collect_text_styles(node)

            # Apply styles and write each line
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if y + i >= output.height:
                    break
                # Apply transformers
                transformed = line
                for fn in new_transformers:
                    transformed = fn(transformed, i)
                # Apply text styles
                if style_props and transformed:
                    transformed = style_text(transformed, **style_props)
                output.write(x, y + i, transformed)

        return

    clipped = False

    if node.node_name == "ink-box":
        # Render background (matching Ink's renderBackground)
        _render_background(node, output, x, y, w, h)

        # Render border (matching Ink's renderBorder)
        render_border(x, y, node.style, w, h, output)

        # Overflow clipping (matching Ink's clip logic)
        clip_h = node.style.get("overflow_x") == "hidden" or node.style.get("overflow") == "hidden"
        clip_v = node.style.get("overflow_y") == "hidden" or node.style.get("overflow") == "hidden"

        if clip_h or clip_v:
            x1 = x + int(yn.get_computed_border(yoga.Edge.Left)) if clip_h else 0
            x2 = x + w - int(yn.get_computed_border(yoga.Edge.Right)) if clip_h else output.width
            y1 = y + int(yn.get_computed_border(yoga.Edge.Top)) if clip_v else 0
            y2 = y + h - int(yn.get_computed_border(yoga.Edge.Bottom)) if clip_v else output.height
            output.clip(x1, x2, y1, y2)
            clipped = True

    # Render children (for ink-root and ink-box)
    if node.node_name in ("ink-root", "ink-box"):
        for child in node.children:
            _render_node(
                child, output, x, y,
                transformers=new_transformers,
                skip_static=skip_static,
                only_static=only_static,
            )

        if clipped:
            output.unclip()


def _render_background(
    node: DOMElement, output: Output, x: int, y: int, w: int, h: int
) -> None:
    """Render background color matching Ink's render-background.ts exactly."""
    bg = (
        node.style.get("background_color")
        or node.style.get("bg_color")
        or node.style.get("background")
    )
    if not bg:
        return

    border_style = node.style.get("border_style")
    left_bw = 1 if border_style and node.style.get("border_left", True) is not False else 0
    right_bw = 1 if border_style and node.style.get("border_right", True) is not False else 0
    top_bw = 1 if border_style and node.style.get("border_top", True) is not False else 0
    bottom_bw = 1 if border_style and node.style.get("border_bottom", True) is not False else 0

    content_w = w - left_bw - right_bw
    content_h = h - top_bw - bottom_bw

    if content_w <= 0 or content_h <= 0:
        return

    bg_line = style_text(" " * content_w, background_color=bg)
    for row in range(content_h):
        output.write(x + left_bw, y + top_bw + row, bg_line)


def _apply_padding_to_text(node: DOMElement, text: str) -> str:
    """Apply padding offset to text. Matches Ink's applyPaddingToText.

    Takes X and Y of the first child's yoga node and uses them as offset.
    """
    if node.children:
        first_child = node.children[0]
        if isinstance(first_child, DOMElement) and first_child.yoga_node:
            offset_x = int(first_child.yoga_node.layout_left)
            offset_y = int(first_child.yoga_node.layout_top)
            text = "\n" * offset_y + (" " * offset_x + text if offset_x > 0 else text)

    return text


def _get_max_width(yoga_node: Any) -> int:
    """Get max content width from yoga node. Matches Ink's getMaxWidth."""
    return int(
        yoga_node.get_computed_width()
        - yoga_node.get_computed_padding(yoga.Edge.Left)
        - yoga_node.get_computed_padding(yoga.Edge.Right)
        - yoga_node.get_computed_border(yoga.Edge.Left)
        - yoga_node.get_computed_border(yoga.Edge.Right)
    )


def _widest_line(text: str) -> int:
    """Width of the widest line in a multi-line string."""
    max_w = 0
    for line in text.split("\n"):
        w = visible_width(line)
        if w > max_w:
            max_w = w
    return max_w


def _collect_text_styles(node: DOMElement) -> dict[str, Any]:
    """Collect text style props from node and parent text nodes."""
    style_props: dict[str, Any] = {}
    for key in (
        "color", "bold", "dim", "dim_color", "italic", "underline",
        "strikethrough", "inverse", "overline", "background_color",
        "bg_color", "background",
    ):
        if key in node.style:
            style_props[key] = node.style[key]

    # Inherit from parent text nodes
    parent = node.parent
    while parent and parent.node_name == "ink-text":
        for key in (
            "color", "bold", "dim", "dim_color", "italic", "underline",
            "strikethrough", "inverse", "overline", "background_color",
            "bg_color", "background",
        ):
            if key in parent.style and key not in style_props:
                style_props[key] = parent.style[key]
        parent = parent.parent

    return style_props


def _wrap_text_with_mode(text: str, max_width: int, wrap_mode: str) -> str:
    """Wrap/truncate text matching Ink's wrapText."""
    def _apply(fn, text, mw):
        lines = text.split("\n")
        return "\n".join(
            fn(line, mw) if visible_width(line) > mw else line for line in lines
        )

    if wrap_mode in ("truncate", "truncate-end", "truncate_end"):
        return _apply(_truncate, text, max_width)
    elif wrap_mode in ("truncate-start", "truncate_start"):
        return _apply(_truncate_start, text, max_width)
    elif wrap_mode in ("truncate-middle", "truncate_middle"):
        return _apply(_truncate_middle, text, max_width)
    elif wrap_mode == "hard":
        return "\n".join(_wrap_text_hard(text, max_width))
    else:
        # Default "wrap": word wrap
        return "\n".join(_wrap_text(text, max_width))


def _wrap_text_hard(text: str, max_width: int) -> list[str]:
    """Hard wrap at exact character position."""
    if max_width <= 0:
        return [text]
    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        pos = 0
        while pos < len(raw_line):
            end = pos
            w = 0
            while end < len(raw_line):
                cw = visible_width(raw_line[end])
                if w + cw > max_width:
                    break
                w += cw
                end += 1
            lines.append(raw_line[pos:end])
            pos = end
    return lines if lines else [""]


def _truncate(text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    result = ""
    w = 0
    for ch in text:
        cw = visible_width(ch)
        if w + cw > max_width:
            break
        result += ch
        w += cw
    return result


def _truncate_start(text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    result = ""
    w = 0
    for ch in reversed(list(text)):
        cw = visible_width(ch)
        if w + cw > max_width:
            break
        result = ch + result
        w += cw
    return result


def _truncate_middle(text: str, max_width: int) -> str:
    if max_width <= 3:
        return _truncate(text, max_width)
    half = (max_width - 1) // 2
    start = _truncate(text, half)
    end = _truncate_start(text, max_width - half - 1)
    return start + "\u2026" + end
