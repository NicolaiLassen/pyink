"""Tests for the @component decorator."""
from pyink.component import component
from pyink.vnode import Box, Text, VNode


def test_component_returns_vnode():
    @component
    def my_comp(label="hello"):
        return Box(Text(label))

    result = my_comp(label="world")
    assert isinstance(result, VNode)
    assert result.type is my_comp._original_fn
    assert result.props == {"label": "world"}


def test_component_with_children():
    @component
    def wrapper():
        return Box()

    result = wrapper(Text("child1"), Text("child2"))
    assert len(result.children) == 2


def test_component_key():
    @component
    def item():
        return Text("item")

    result = item(key="abc")
    assert result.key == "abc"
    assert "key" not in result.props


def test_component_is_component_flag():
    @component
    def my_comp():
        return Box()

    assert my_comp._is_component is True
