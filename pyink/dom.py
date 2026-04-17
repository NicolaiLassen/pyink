"""Virtual DOM types and manipulation functions.

1:1 port of Ink's ``src/dom.ts``.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pyyoga as yoga


@dataclass(eq=False)
class TextNode:
    """A text content node in the virtual DOM.

    Port of Ink's ``TextNode`` type (dom.ts lines 75–78).
    """

    value: str = ""
    parent: DOMElement | None = None
    yoga_node: yoga.Node | None = None  # Always None for text nodes
    style: dict[str, Any] = field(default_factory=dict)

    @property
    def node_name(self) -> str:
        return "#text"


@dataclass(eq=False)
class DOMElement:
    """An element node in the virtual DOM, with an attached yoga layout node.

    Port of Ink's ``DOMElement`` type (dom.ts lines 27–73).
    """

    node_name: str = "ink-box"
    style: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list[DOMElement | TextNode] = field(default_factory=list)
    parent: DOMElement | None = None
    yoga_node: yoga.Node | None = None

    # Output transformer function (set by Transform component)
    internal_transform: Any = None

    # Marks this node as a <Static> element
    internal_static: bool = False

    # Accessibility metadata (role + state)
    # Port of Ink's internal_accessibility (dom.ts lines 33–63)
    internal_accessibility: dict[str, Any] = field(default_factory=dict)

    # Root-node-only fields (dom.ts lines 67–71)
    is_static_dirty: bool = False
    static_node: DOMElement | None = None
    on_compute_layout: Callable[[], None] | None = None
    on_render: Callable[[], None] | None = None
    on_immediate_render: Callable[[], None] | None = None

    # Layout listeners (dom.ts line 72)
    internal_layout_listeners: set[Callable[[], None]] | None = None


    def __post_init__(self) -> None:
        if self.yoga_node is None and self.node_name != "ink-virtual-text":
            self.yoga_node = yoga.Node()


DOMNode = DOMElement | TextNode


def create_node(node_name: str) -> DOMElement:
    """Create a new DOM element with the given node name.

    Port of Ink's ``createNode`` (dom.ts lines 92–109).

    Parameters
    ----------
    node_name : str
        The element tag name (e.g. ``"ink-root"``, ``"ink-box"``,
        ``"ink-text"``, ``"ink-virtual-text"``).

    Returns
    -------
    DOMElement
        The newly created element.
    """
    node = DOMElement(
        node_name=node_name,
        yoga_node=None if node_name == "ink-virtual-text" else yoga.Node(),
    )

    if node_name == "ink-text" and node.yoga_node is not None:
        node.yoga_node.set_measure_func(
            lambda w, wm, h, hm: _measure_text_node(node, w, wm, h, hm)
        )

    return node


# Keep old name as alias for backwards compatibility
create_element = create_node


def create_text_node(text: str) -> TextNode:
    """Create a new text node with the given content.

    Port of Ink's ``createTextNode`` (dom.ts lines 205–217).

    Parameters
    ----------
    text : str
        The text content for the node.

    Returns
    -------
    TextNode
        The newly created text node.
    """
    node = TextNode(value=text)
    set_text_node_value(node, text)
    return node


def append_child(parent: DOMElement, child: DOMNode) -> None:
    """Append a child node to a parent element.

    Port of Ink's ``appendChildNode`` (dom.ts lines 111–132).

    Parameters
    ----------
    parent : DOMElement
        The parent element to append to.
    child : DOMNode
        The child node to append.
    """
    # Remove from old parent first (Ink line 115–117)
    if child.parent is not None:
        remove_child(child.parent, child)

    child.parent = parent
    parent.children.append(child)

    if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
        parent.yoga_node.add_child(child.yoga_node)

    if parent.node_name in ("ink-text", "ink-virtual-text"):
        mark_node_as_dirty(parent)


def remove_child(parent: DOMElement, child: DOMNode) -> None:
    """Remove a child node from a parent element.

    Port of Ink's ``removeChildNode`` (dom.ts lines 167–185).

    Parameters
    ----------
    parent : DOMElement
        The parent element to remove from.
    child : DOMNode
        The child node to remove.
    """
    if isinstance(child, DOMElement) and child.yoga_node:
        if child.parent and child.parent.yoga_node:
            child.parent.yoga_node.remove_child(child.yoga_node)

    child.parent = None

    if child in parent.children:
        parent.children.remove(child)

    if parent.node_name in ("ink-text", "ink-virtual-text"):
        mark_node_as_dirty(parent)


def insert_before(
    parent: DOMElement, child: DOMNode, before: DOMNode
) -> None:
    """Insert a child node before another child in the parent element.

    Port of Ink's ``insertBeforeNode`` (dom.ts lines 134–165).

    Parameters
    ----------
    parent : DOMElement
        The parent element to insert into.
    child : DOMNode
        The child node to insert.
    before : DOMNode
        The existing child to insert before.
    """
    # Remove from old parent first (Ink line 139–140)
    if child.parent is not None:
        remove_child(child.parent, child)

    child.parent = parent

    index = -1
    try:
        index = parent.children.index(before)
    except ValueError:
        pass

    if index >= 0:
        parent.children.insert(index, child)
        if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
            parent.yoga_node.insert_child(child.yoga_node, index)
    else:
        parent.children.append(child)
        if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
            parent.yoga_node.add_child(child.yoga_node)

    if parent.node_name in ("ink-text", "ink-virtual-text"):
        mark_node_as_dirty(parent)


def set_attribute(node: DOMElement, key: str, value: Any) -> None:
    """Set an attribute on a DOM element.

    Port of Ink's ``setAttribute`` (dom.ts lines 187–198).

    Parameters
    ----------
    node : DOMElement
        The element to set the attribute on.
    key : str
        The attribute name.
    value : Any
        The attribute value.
    """
    if key == "internal_accessibility":
        node.internal_accessibility = value if isinstance(value, dict) else {}
        return

    node.attributes[key] = value


def set_style(node: DOMNode, style: dict[str, Any] | None = None) -> None:
    """Set the style on a DOM node.

    Port of Ink's ``setStyle`` (dom.ts lines 200–203).

    Parameters
    ----------
    node : DOMNode
        The node to set the style on.
    style : dict or None
        The style dictionary. Defaults to empty dict if None.
    """
    node.style = style if style is not None else {}


def set_text_node_value(node: TextNode, text: str) -> None:
    """Set the text value of a TextNode and mark its parent as dirty.

    Port of Ink's ``setTextNodeValue`` (dom.ts lines 259–266).

    Parameters
    ----------
    node : TextNode
        The text node to update.
    text : str
        The new text value.
    """
    if not isinstance(text, str):
        text = str(text)

    node.value = text
    mark_node_as_dirty(node)


def find_closest_yoga_node(node: DOMNode | None) -> yoga.Node | None:
    """Walk up the parent chain to find the nearest node with a yoga node.

    Port of Ink's ``findClosestYogaNode`` (dom.ts lines 245–251).

    Parameters
    ----------
    node : DOMNode or None
        The starting node.

    Returns
    -------
    yoga.Node or None
        The closest yoga layout node, or None if none found.
    """
    if node is None or node.parent is None:
        return None

    if isinstance(node, DOMElement) and node.yoga_node:
        return node.yoga_node

    return find_closest_yoga_node(node.parent)


def mark_node_as_dirty(node: DOMNode | None) -> None:
    """Mark the closest yoga node as dirty to trigger re-measurement.

    Port of Ink's ``markNodeAsDirty`` (dom.ts lines 253–257).

    Parameters
    ----------
    node : DOMNode or None
        The node whose nearest yoga ancestor should be marked dirty.
    """
    yoga_node = find_closest_yoga_node(node)
    if yoga_node is not None:
        try:
            yoga_node.mark_dirty()
        except Exception:
            # Node may not have a measure func set (required for markDirty)
            pass


def add_layout_listener(
    root_node: DOMElement, listener: Callable[[], None]
) -> Callable[[], None]:
    """Register a layout listener on the root node.

    Port of Ink's ``addLayoutListener`` (dom.ts lines 268–282).

    Parameters
    ----------
    root_node : DOMElement
        The root (``ink-root``) element.
    listener : callable
        The callback to invoke after layout computation.

    Returns
    -------
    callable
        An unsubscribe function that removes the listener.
    """
    if root_node.node_name != "ink-root":
        return lambda: None

    if root_node.internal_layout_listeners is None:
        root_node.internal_layout_listeners = set()

    root_node.internal_layout_listeners.add(listener)

    def unsubscribe() -> None:
        if root_node.internal_layout_listeners is not None:
            root_node.internal_layout_listeners.discard(listener)

    return unsubscribe


def emit_layout_listeners(root_node: DOMElement) -> None:
    """Emit all registered layout listeners on the root node.

    Port of Ink's ``emitLayoutListeners`` (dom.ts lines 284–292).

    Parameters
    ----------
    root_node : DOMElement
        The root (``ink-root``) element.
    """
    if root_node.node_name != "ink-root" or not root_node.internal_layout_listeners:
        return

    for listener in root_node.internal_layout_listeners:
        listener()


def squash_text_nodes(element: DOMElement) -> str:
    """Collect all text content from an ink-text element's children.

    Port of Ink's ``squashTextNodes`` (squash-text-nodes.ts).
    Handles ``ink-text``, ``ink-virtual-text``, applies
    ``internal_transform``, and sanitizes ANSI sequences.

    Parameters
    ----------
    element : DOMElement
        The ink-text element whose text content to collect.

    Returns
    -------
    str
        The concatenated text content with sanitized ANSI.
    """
    text = ""

    for index, child in enumerate(element.children):
        if isinstance(child, TextNode):
            text += child.value
        elif isinstance(child, DOMElement) and child.node_name in (
            "ink-text",
            "ink-virtual-text",
        ):
            node_text = squash_text_nodes(child)

            # Apply child's internal_transform if present
            # (Ink squash-text-nodes.ts lines 34–39)
            if node_text and callable(child.internal_transform):
                node_text = child.internal_transform(node_text, index)

            text += node_text

    # Port of squash-text-nodes.ts line 45: return sanitizeAnsi(text)
    from pyink.renderer.sanitize_ansi import sanitize_ansi

    return sanitize_ansi(text)


# ── Internal helpers ──


def _measure_text_node(
    node: DOMNode,
    width: float,
    width_mode: int,
    height: float,
    height_mode: int,
) -> tuple[float, float]:
    """Yoga measure function for text nodes.

    Port of Ink's ``measureTextNode`` (dom.ts lines 219–243).

    Parameters
    ----------
    node : DOMNode
        The DOM node being measured.
    width : float
        Available width from Yoga.
    width_mode : int
        Yoga MeasureMode for width.
    height : float
        Available height from Yoga.
    height_mode : int
        Yoga MeasureMode for height.

    Returns
    -------
    tuple[float, float]
        (measured_width, measured_height)
    """
    if isinstance(node, TextNode):
        text = node.value
    else:
        text = squash_text_nodes(node)

    dimensions = _measure_text(text)

    # Text fits into container, no need to wrap
    if dimensions[0] <= width:
        return dimensions

    # Box is shrinking and asking if text fits in <1px — say no
    if dimensions[0] >= 1 and width > 0 and width < 1:
        return dimensions

    text_wrap = node.style.get("text_wrap", "wrap") if hasattr(node, "style") else "wrap"
    wrapped_text = _wrap_text_for_measure(text, width, text_wrap)

    return _measure_text(wrapped_text)


def _measure_text(text: str) -> tuple[float, float]:
    """Measure text dimensions (width, height).

    Port of Ink's ``measureText`` (measure-text.ts).

    Parameters
    ----------
    text : str
        The text to measure.

    Returns
    -------
    tuple[float, float]
        (widest_line_width, line_count)
    """
    if len(text) == 0:
        return (0.0, 0.0)

    width = _widest_line(text)
    height = text.count("\n") + 1
    return (float(width), float(height))


def _widest_line(text: str) -> int:
    """Get the visible width of the widest line in text.

    Parameters
    ----------
    text : str
        Text that may contain ANSI escape codes and multiple lines.

    Returns
    -------
    int
        Visible width (in terminal columns) of the widest line,
        accounting for CJK wide characters.
    """
    from pyink.text_wrap import visible_width as _vw

    return max((_vw(line) for line in text.split("\n")), default=0)


def _wrap_text_for_measure(
    text: str, max_width: float, wrap_type: str
) -> str:
    """Wrap text for measurement purposes.

    Delegates to ``pyink.text_wrap`` so the measure path and the render
    path use the same wrapping logic. Without this sharing, yoga may
    allocate N lines but the renderer produces N+1, causing sibling
    items to overlap.

    Parameters
    ----------
    text : str
        The text to wrap.
    max_width : float
        Maximum visible width per line. ``0`` or negative means no limit.
    wrap_type : str
        The wrap mode (``"wrap"``, ``"hard"``, ``"truncate"``, etc.).

    Returns
    -------
    str
        The wrapped text, with ``\\n`` separating wrapped lines.
    """
    from pyink.text_wrap import wrap_text

    max_w = int(max_width) if max_width > 0 else 999

    if wrap_type in ("truncate", "truncate-middle", "truncate-start",
                     "truncate-end", "truncate_middle", "truncate_start",
                     "truncate_end"):
        # Truncation doesn't change height for measurement
        return text

    return "\n".join(wrap_text(text, max_w, wrap_type or "wrap"))
