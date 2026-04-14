from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pyyoga as yoga


@dataclass
class TextNode:
    """A text content node in the virtual DOM."""

    value: str = ""
    parent: DOMElement | None = None

    @property
    def node_name(self) -> str:
        return "#text"


@dataclass
class DOMElement:
    """An element node in the virtual DOM, with an attached yoga layout node."""

    node_name: str = "ink-box"
    style: dict[str, Any] = field(default_factory=dict)
    children: list[DOMElement | TextNode] = field(default_factory=list)
    parent: DOMElement | None = None
    yoga_node: yoga.Node | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    internal_transform: Any = None

    def __post_init__(self) -> None:
        if self.yoga_node is None:
            self.yoga_node = yoga.Node()


DOMNode = DOMElement | TextNode


def create_element(node_name: str, **style: Any) -> DOMElement:
    """Create a new DOM element with the given node name and style.

    Parameters
    ----------
    node_name : str
        The element tag name (e.g. ``"ink-box"``, ``"ink-text"``).
    **style : Any
        Style properties to apply to the element.

    Returns
    -------
    DOMElement
        The newly created element.
    """
    el = DOMElement(node_name=node_name, style=style)
    return el


def create_text_node(text: str) -> TextNode:
    """Create a new text node with the given content.

    Parameters
    ----------
    text : str
        The text content for the node.

    Returns
    -------
    TextNode
        The newly created text node.
    """
    return TextNode(value=text)


def append_child(parent: DOMElement, child: DOMNode) -> None:
    """Append a child node to a parent element.

    Also wires up the underlying yoga layout node if both parent and
    child are DOMElements with yoga nodes.

    Parameters
    ----------
    parent : DOMElement
        The parent element to append to.
    child : DOMNode
        The child node to append.
    """
    child.parent = parent
    parent.children.append(child)

    if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
        parent.yoga_node.add_child(child.yoga_node)


def remove_child(parent: DOMElement, child: DOMNode) -> None:
    """Remove a child node from a parent element.

    Also removes the yoga layout relationship if applicable.

    Parameters
    ----------
    parent : DOMElement
        The parent element to remove from.
    child : DOMNode
        The child node to remove.
    """
    if child in parent.children:
        parent.children.remove(child)
        child.parent = None

        if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
            parent.yoga_node.remove_child(child.yoga_node)


def insert_before(
    parent: DOMElement, child: DOMNode, before: DOMNode
) -> None:
    """Insert a child node before another child in the parent element.

    Parameters
    ----------
    parent : DOMElement
        The parent element to insert into.
    child : DOMNode
        The child node to insert.
    before : DOMNode
        The existing child to insert before.
    """
    child.parent = parent
    idx = parent.children.index(before)
    parent.children.insert(idx, child)

    if isinstance(child, DOMElement) and child.yoga_node and parent.yoga_node:
        # Rebuild yoga child order
        _sync_yoga_children(parent)


def _sync_yoga_children(parent: DOMElement) -> None:
    if not parent.yoga_node:
        return
    parent.yoga_node.remove_all_children()
    for child in parent.children:
        if isinstance(child, DOMElement) and child.yoga_node:
            parent.yoga_node.add_child(child.yoga_node)


def squash_text_nodes(element: DOMElement) -> str:
    """Collect all text content from an ink-text element's children.

    Parameters
    ----------
    element : DOMElement
        The ink-text element whose text content to collect.

    Returns
    -------
    str
        The concatenated text content.
    """
    parts: list[str] = []
    for child in element.children:
        if isinstance(child, TextNode):
            parts.append(child.value)
        elif isinstance(child, DOMElement) and child.node_name == "ink-text":
            parts.append(squash_text_nodes(child))
    return "".join(parts)
