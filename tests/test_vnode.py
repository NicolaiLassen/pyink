"""Tests for VNode types and element factories."""
from pyink.vnode import Box, Text, Spacer, Newline, Static, Transform, VNode


def test_box_creates_vnode():
    node = Box(Text("hello"), flex_direction="row")
    assert node.type == "ink-box"
    assert node.props["flex_direction"] == "row"
    assert len(node.children) == 1


def test_text_creates_vnode():
    node = Text("hello", color="green", bold=True)
    assert node.type == "ink-text"
    assert node.props["color"] == "green"
    assert node.props["bold"] is True
    assert node.children == ["hello"]


def test_spacer_has_flex_grow():
    node = Spacer()
    assert node.type == "ink-box"
    assert node.props["flex_grow"] == 1


def test_newline():
    node = Newline(count=3)
    assert node.type == "ink-text"
    assert node.children == ["\n\n\n"]


def test_static_with_items():
    items = ["a", "b", "c"]
    node = Static(items=items, render_item=lambda item, i: Text(item, key=i))
    assert node.props["_static"] is True
    assert len(node.children) == 3


def test_transform():
    fn = lambda text, idx: text.upper()
    node = Transform(Text("hello"), transform=fn)
    assert node.props["_transform"] is fn


def test_key_prop():
    node = Box(key="my-key")
    assert node.key == "my-key"
    assert "key" not in node.props


def test_nested_children():
    node = Box(
        Box(Text("a"), Text("b")),
        Box(Text("c")),
    )
    assert len(node.children) == 2
    assert len(node.children[0].children) == 2
