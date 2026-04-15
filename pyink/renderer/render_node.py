"""Render pipeline matching Ink's render-node-to-output.ts and renderer.ts.

Walks the DOM tree, applies yoga layout positions, renders borders,
backgrounds, text with wrapping/truncation, and overflow clipping.
"""
from __future__ import annotations

import re as _re
import shutil
from collections.abc import Callable
from typing import Any

import pyyoga as yoga

from pyink.dom import DOMElement, TextNode, squash_text_nodes
from pyink.layout.engine import _wrap_text, compute_layout, visible_width
from pyink.renderer.ansi import style_text
from pyink.renderer.borders import render_border
from pyink.renderer.output import Output


def render_node_to_screen_reader_output(
    node: DOMElement,
    *,
    parent_role: str | None = None,
    skip_static_elements: bool = False,
) -> str:
    """Render a DOM tree to screen-reader-friendly text output.

    Port of Ink's ``renderNodeToScreenReaderOutput``
    (render-node-to-output.ts lines 32–97).

    Parameters
    ----------
    node : DOMElement
        The root node to render.
    parent_role : str or None
        The accessibility role of the parent node.
    skip_static_elements : bool
        Whether to skip internal_static subtrees.

    Returns
    -------
    str
        Screen reader text output.
    """
    if skip_static_elements and node.internal_static:
        return ""

    # Check display none
    if node.yoga_node:
        try:
            if node.yoga_node.get_display() == yoga.Display.None_:
                return ""
        except Exception:
            pass

    output = ""

    if node.node_name == "ink-text":
        output = squash_text_nodes(node)
    elif node.node_name in ("ink-box", "ink-root"):
        flex_dir = node.style.get("flex_direction", "column")
        separator = " " if flex_dir in ("row", "row-reverse") else "\n"

        child_nodes = list(node.children)
        if flex_dir in ("row-reverse", "column-reverse"):
            child_nodes = list(reversed(child_nodes))

        parts = []
        for child_node in child_nodes:
            if isinstance(child_node, TextNode):
                continue
            if isinstance(child_node, DOMElement):
                sr_output = render_node_to_screen_reader_output(
                    child_node,
                    parent_role=node.internal_accessibility.get("role"),
                    skip_static_elements=skip_static_elements,
                )
                if sr_output:
                    parts.append(sr_output)

        output = separator.join(parts)

    # Apply accessibility annotations
    accessibility = node.internal_accessibility
    if accessibility:
        state = accessibility.get("state")
        if state and isinstance(state, dict):
            state_keys = [k for k, v in state.items() if v]
            state_desc = ", ".join(state_keys)
            if state_desc:
                output = f"({state_desc}) {output}"

        role = accessibility.get("role")
        if role and role != parent_role:
            output = f"{role}: {output}"

    return output


class RenderResult:
    """Result of a render pass."""

    def __init__(self, output: str, output_height: int, static_output: str = "") -> None:
        self.output = output
        self.output_height = output_height
        self.static_output = static_output


def renderer(
    dom: DOMElement | None,
    width: int | None = None,
    is_screen_reader_enabled: bool = False,
) -> RenderResult:
    """Render the DOM tree with static/dynamic separation.

    Port of Ink's ``renderer.ts``. Branches between screen-reader
    output and normal visual output.

    Parameters
    ----------
    dom : DOMElement or None
        Root DOM element.
    width : int, optional
        Terminal width override.
    is_screen_reader_enabled : bool
        Use screen-reader-friendly text output.

    Returns
    -------
    RenderResult
        Contains ``output`` (dynamic), ``output_height``, and
        ``static_output`` (content to write once to scrollback).
    """
    if dom is None or dom.yoga_node is None:
        return RenderResult("", 0)

    if width is None:
        try:
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 80

    compute_layout(dom, width)

    # Screen reader path (port of renderer.ts lines 14–35)
    if is_screen_reader_enabled:
        output = render_node_to_screen_reader_output(
            dom, skip_static_elements=True
        )
        output_height = output.count("\n") + 1 if output else 0

        static_output = ""
        if dom.static_node and isinstance(dom.static_node, DOMElement):
            static_output = render_node_to_screen_reader_output(
                dom.static_node, skip_static_elements=False
            )

        return RenderResult(
            output=output,
            output_height=output_height,
            static_output=f"{static_output}\n" if static_output else "",
        )

    yn = dom.yoga_node
    output_width = int(yn.get_computed_width())
    output_height = int(yn.get_computed_height())

    # Main render — skip static elements.
    output_buf = Output(output_width, output_height)
    _render_node(dom, output_buf, 0, 0, transformers=[], mode="dynamic")
    generated_output, gen_height = output_buf.get()

    # Static render — use dom.static_node (separate DOM tree, like Ink).
    static_output = ""
    if dom.static_node and isinstance(dom.static_node, DOMElement) and dom.static_node.yoga_node:
        sn = dom.static_node
        sw = int(sn.yoga_node.get_computed_width()) or output_width
        sh = int(sn.yoga_node.get_computed_height()) or 1
        static_buf = Output(sw, sh)
        _render_node(sn, static_buf, 0, 0, transformers=[], mode="all")
        static_raw, _sh = static_buf.get()
        static_raw = static_raw.rstrip("\n")
        if static_raw.strip():
            static_output = static_raw + "\n"


    return RenderResult(
        output=generated_output,
        output_height=gen_height,
        static_output=static_output,
    )


def render_to_string(dom: DOMElement | None, width: int | None = None) -> str:
    """Convenience wrapper — returns just the output string."""
    result = renderer(dom, width)
    return result.output


def _render_node(
    node: DOMElement | TextNode,
    output: Output,
    offset_x: int,
    offset_y: int,
    *,
    transformers: list[Callable] | None = None,
    mode: str = "all",
) -> None:
    """Recursively render a DOM node to the output buffer.

    Parameters
    ----------
    mode : str
        ``"all"`` renders everything, ``"static"`` renders only
        ``_static`` subtrees, ``"dynamic"`` skips ``_static`` nodes.
    """
    if isinstance(node, TextNode):
        return

    yn = node.yoga_node
    if yn is None:
        return

    display = node.style.get("display")
    if display == "none":
        return

    # Check display via yoga node too (for hideInstance/unhideInstance)
    try:
        if yn.get_display() == yoga.Display.None_:
            return
    except Exception:
        pass

    is_static = node.internal_static

    if mode == "dynamic" and is_static:
        return

    if mode == "static":
        if is_static:
            # Found a static subtree — render children normally.
            mode = "all"
        elif node.node_name in ("ink-root", "ink-box"):
            # Not static — recurse to find static children.
            for child in node.children:
                _render_node(
                    child, output, offset_x, offset_y,
                    transformers=transformers,
                    mode="static",
                )
            return
        else:
            return

    # Left and top positions are relative to parent (matching Ink)
    x = offset_x + int(yn.layout_left)
    y = offset_y + int(yn.layout_top)
    w = int(yn.layout_width)
    h = int(yn.layout_height)

    # Transformers chain (matching Ink: prepend internal_transform)
    new_transformers = list(transformers or [])
    if callable(node.internal_transform):
        new_transformers = [node.internal_transform] + new_transformers

    if node.node_name == "ink-text":
        text = squash_text_nodes(node)

        if len(text) > 0:
            current_width = _widest_line(text)
            max_width = _get_max_width(yn)

            if current_width > max_width:
                text_wrap = node.style.get("text_wrap", "wrap")
                text = _wrap_text_with_mode(text, max_width, text_wrap)

            text = _apply_padding_to_text(node, text)

            # Collect text styles and apply to the full text block
            style_props = _collect_text_styles(node)
            if style_props and text:
                text = style_text(text, **style_props)

            # Write text with transformers (Ink passes transformers to output.write)
            output.write(x, y, text, transformers=new_transformers)

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
                mode=mode,
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
        output.write(x + left_bw, y + top_bw + row, bg_line, transformers=[])


def _apply_padding_to_text(node: DOMElement, text: str) -> str:
    """Apply padding offset to text. Matches Ink's applyPaddingToText."""
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
    """Collect text style props from node and parent text nodes.

    Also implements BackgroundContext: if no explicit background_color
    is set on the text, walk up to find the nearest ancestor Box with
    a background_color and inherit it (port of Ink's BackgroundContext).
    """
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
    while parent and parent.node_name in ("ink-text", "ink-virtual-text"):
        for key in (
            "color", "bold", "dim", "dim_color", "italic", "underline",
            "strikethrough", "inverse", "overline", "background_color",
            "bg_color", "background",
        ):
            if key in parent.style and key not in style_props:
                style_props[key] = parent.style[key]
        parent = parent.parent

    # Port of Ink's BackgroundContext (Box.tsx lines 102-109, Text.tsx lines 86,104-107):
    # If no explicit background_color on text, inherit from nearest ancestor Box
    has_bg = any(
        k in style_props for k in ("background_color", "bg_color", "background")
    )
    if not has_bg and parent:
        ancestor = parent
        while ancestor:
            if ancestor.node_name == "ink-box":
                inherited_bg = (
                    ancestor.style.get("background_color")
                    or ancestor.style.get("bg_color")
                    or ancestor.style.get("background")
                )
                if inherited_bg:
                    style_props["background_color"] = inherited_bg
                    break
            ancestor = ancestor.parent

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
        return "\n".join(_wrap_text(text, max_width))


# Comprehensive ANSI regex for tokenizing text into (ansi_seq | char) chunks.
_ANSI_TOKEN_RE = _re.compile(
    r"(\x1b\[[0-9;:]*[a-zA-Z]"
    r"|\x1b\[\?[0-9;]*[a-zA-Z]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[NOPc]"
    r"|\x9b[0-9;:]*[a-zA-Z])"
)


def _ansi_tokenize(text: str) -> list[tuple[str, int]]:
    """Split text into (chunk, visible_width) pairs.

    ANSI escape sequences get width 0. Visible characters get their
    display width (2 for CJK wide chars, 1 otherwise).
    """
    result: list[tuple[str, int]] = []
    last = 0
    for m in _ANSI_TOKEN_RE.finditer(text):
        # Plain text before this ANSI sequence
        start, end = m.start(), m.end()
        if start > last:
            for ch in text[last:start]:
                result.append((ch, _visible_char_width(ch)))
        # The ANSI sequence itself (zero width)
        result.append((m.group(0), 0))
        last = end
    # Remaining plain text
    if last < len(text):
        for ch in text[last:]:
            result.append((ch, _visible_char_width(ch)))
    return result


def _visible_char_width(ch: str) -> int:
    """Width of a single visible character."""
    import unicodedata
    try:
        eaw = unicodedata.east_asian_width(ch)
        return 2 if eaw in ("W", "F") else 1
    except Exception:
        return 1


def _wrap_text_hard(text: str, max_width: int) -> list[str]:
    """Hard wrap at exact character position, ANSI-aware."""
    if max_width <= 0:
        return [text]
    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        tokens = _ansi_tokenize(raw_line)
        current: list[str] = []
        w = 0
        for chunk, cw in tokens:
            if cw == 0:
                # ANSI sequence — always include, doesn't affect width
                current.append(chunk)
            elif w + cw > max_width:
                lines.append("".join(current))
                current = [chunk]
                w = cw
            else:
                current.append(chunk)
                w += cw
        if current:
            lines.append("".join(current))
    return lines if lines else [""]


def _truncate(text: str, max_width: int) -> str:
    """Truncate text at max_width, ANSI-aware."""
    if max_width <= 0:
        return ""
    tokens = _ansi_tokenize(text)
    result: list[str] = []
    w = 0
    for chunk, cw in tokens:
        if cw == 0:
            result.append(chunk)
        elif w + cw > max_width:
            break
        else:
            result.append(chunk)
            w += cw
    return "".join(result)


def _truncate_start(text: str, max_width: int) -> str:
    """Truncate from the start, keeping the last max_width columns, ANSI-aware."""
    if max_width <= 0:
        return ""
    tokens = _ansi_tokenize(text)
    result: list[str] = []
    w = 0
    for chunk, cw in reversed(tokens):
        if cw == 0:
            result.append(chunk)
        elif w + cw > max_width:
            break
        else:
            result.append(chunk)
            w += cw
    result.reverse()
    return "".join(result)


def _truncate_middle(text: str, max_width: int) -> str:
    """Truncate from the middle with ellipsis, ANSI-aware."""
    if max_width <= 3:
        return _truncate(text, max_width)
    half = (max_width - 1) // 2
    start = _truncate(text, half)
    end = _truncate_start(text, max_width - half - 1)
    return start + "\u2026" + end
