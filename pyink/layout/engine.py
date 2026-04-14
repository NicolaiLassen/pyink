"""Layout computation engine using pyyoga (Yoga).

Port of Ink's layout computation patterns. Works with the DOM layer
where yoga nodes are created and measure funcs are set at node
creation time (in ``dom.py``).
"""
from __future__ import annotations

import re

import pyyoga as yoga

from pyink.dom import DOMElement, squash_text_nodes
from pyink.layout.styles import apply_styles

# Regex to strip ANSI escape sequences for width measurement
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def visible_width(text: str) -> int:
    """Calculate visible width of a string, ignoring ANSI escape codes.

    Parameters
    ----------
    text : str
        Text that may contain ANSI escape sequences.

    Returns
    -------
    int
        The visible character width, accounting for wide (CJK) characters.
    """
    clean = _ANSI_RE.sub("", text)
    # Handle wide characters (CJK etc.)
    try:
        import unicodedata

        w = 0
        for ch in clean:
            eaw = unicodedata.east_asian_width(ch)
            w += 2 if eaw in ("W", "F") else 1
        return w
    except Exception:
        return len(clean)


def _wrap_text(text: str, max_width: int) -> list[str]:
    """Wrap text to max_width, respecting word boundaries where possible.

    Parameters
    ----------
    text : str
        The text to wrap.
    max_width : int
        Maximum visible width per line.

    Returns
    -------
    list[str]
        The wrapped lines.
    """
    if max_width <= 0:
        return [text]

    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue

        words = raw_line.split(" ")
        current = ""
        for word in words:
            if not current:
                current = word
            elif visible_width(current + " " + word) <= max_width:
                current += " " + word
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)

    return lines if lines else [""]


def _measure_text(
    dom_element: DOMElement,
    width: float,
    width_mode: int,
    height: float,
    height_mode: int,
) -> tuple[float, float]:
    """Yoga measure function for text nodes.

    pyyoga calls this with (width, width_mode, height, height_mode) - no node arg.

    Parameters
    ----------
    dom_element : DOMElement
        The DOM element whose text content is being measured.
    width : float
        Available width provided by Yoga.
    width_mode : int
        Yoga MeasureMode for the width constraint.
    height : float
        Available height provided by Yoga.
    height_mode : int
        Yoga MeasureMode for the height constraint.

    Returns
    -------
    tuple[float, float]
        ``(measured_width, measured_height)`` of the text content.
    """
    text = squash_text_nodes(dom_element)

    wrap_mode = dom_element.style.get("text_wrap") or dom_element.style.get("wrap")
    should_wrap = wrap_mode != "truncate" and wrap_mode is not False

    # width_mode may be int or MeasureMode enum
    is_undefined = (
        width_mode == yoga.MeasureMode.Undefined
        or (isinstance(width_mode, int) and width_mode == int(yoga.MeasureMode.Undefined))
    )
    if should_wrap and not is_undefined:
        max_w = int(width) if width > 0 else 999
    else:
        max_w = 999

    lines = _wrap_text(text, max_w)
    measured_width = max((visible_width(line) for line in lines), default=0)
    measured_height = len(lines)

    return (float(measured_width), float(measured_height))


def build_yoga_tree(element: DOMElement) -> None:
    """Recursively apply styles and rebuild yoga child relationships.

    Yoga nodes are already created and measure funcs set in ``dom.py``
    at node creation time. This function ensures styles are applied
    and parent-child yoga relationships are correct for layout.

    Parameters
    ----------
    element : DOMElement
        The root DOM element to start building from.
    """
    if element.yoga_node is None:
        return

    yn = element.yoga_node

    # Apply style props to yoga node
    apply_styles(yn, element.style)

    # Remove all existing yoga children and re-add in DOM order
    yn.remove_all_children()

    if element.node_name == "ink-text":
        # Text elements use their measure func (set at creation in dom.py).
        # Also set it here in case it was cleared or this is a rebuilt node.
        el = element
        yn.set_measure_func(
            lambda w, wm, h, hm: _measure_text(el, w, wm, h, hm)
        )
    else:
        # Container: recursively build children
        for child in element.children:
            if isinstance(child, DOMElement):
                build_yoga_tree(child)
                if child.yoga_node:
                    yn.add_child(child.yoga_node)


def compute_layout(
    root: DOMElement, terminal_width: int, terminal_height: int | None = None
) -> None:
    """Build yoga tree and compute layout for the entire DOM tree.

    Parameters
    ----------
    root : DOMElement
        The root DOM element.
    terminal_width : int
        Width of the terminal in columns.
    terminal_height : int or None, optional
        Height of the terminal in rows. Currently unused by Yoga
        (Ink doesn't set height on root).
    """
    build_yoga_tree(root)
    if root.yoga_node:
        root.yoga_node.width = terminal_width
        root.yoga_node.calculate_layout()
