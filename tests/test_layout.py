"""Tests for yoga layout integration."""
import pyyoga as yoga

from pyink.dom import DOMElement, TextNode, create_element, create_text_node, append_child
from pyink.layout.engine import compute_layout, visible_width
from pyink.layout.styles import apply_styles


def test_visible_width_ascii():
    assert visible_width("hello") == 5


def test_visible_width_ansi():
    assert visible_width("\x1b[31mred\x1b[0m") == 3


def test_visible_width_cjk():
    # CJK characters are typically double-width
    assert visible_width("你好") == 4


def test_apply_flex_direction():
    node = yoga.Node()
    apply_styles(node, {"flex_direction": "row"})
    assert node.flex_direction == yoga.FlexDirection.Row


def test_apply_padding():
    node = yoga.Node()
    apply_styles(node, {"padding": 2})
    # Verify padding was applied
    assert node.get_padding(yoga.Edge.All).value == 2


def test_apply_margin():
    node = yoga.Node()
    apply_styles(node, {"margin_top": 3})
    assert node.get_margin(yoga.Edge.Top).value == 3


def test_apply_dimensions():
    node = yoga.Node()
    apply_styles(node, {"width": 50, "height": 10})
    node.calculate_layout()
    assert node.get_computed_width() == 50
    assert node.get_computed_height() == 10


def test_compute_layout_basic():
    root = create_element("ink-box")
    child = create_element("ink-text")
    text = create_text_node("Hello")
    append_child(child, text)
    append_child(root, child)

    compute_layout(root, 80, 24)

    assert root.yoga_node.get_computed_width() == 80
    assert child.yoga_node.get_computed_width() > 0


def test_compute_layout_flex_row():
    root = create_element("ink-box")
    root.style["flex_direction"] = "row"

    child1 = create_element("ink-box")
    child1.style["flex_grow"] = 1
    child2 = create_element("ink-box")
    child2.style["flex_grow"] = 1

    # Add text to children so they have content
    t1 = create_element("ink-text")
    append_child(t1, create_text_node("A"))
    append_child(child1, t1)

    t2 = create_element("ink-text")
    append_child(t2, create_text_node("B"))
    append_child(child2, t2)

    append_child(root, child1)
    append_child(root, child2)

    compute_layout(root, 80, 24)

    w1 = child1.yoga_node.get_computed_width()
    w2 = child2.yoga_node.get_computed_width()
    assert w1 == w2  # Equal flex-grow should give equal widths
    assert w1 == 40


def test_border_adds_layout_space():
    root = create_element("ink-box")
    root.style["flex_direction"] = "column"

    child = create_element("ink-box")
    child.style["border_style"] = "single"
    child.style["width"] = 20
    child.style["height"] = 5
    append_child(root, child)

    compute_layout(root, 80, 24)

    w = child.yoga_node.get_computed_width()
    h = child.yoga_node.get_computed_height()
    assert w == 20
    assert h == 5
