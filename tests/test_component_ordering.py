"""Regression tests for component DOM ordering.

Verifies that @component children render in the correct position
relative to host element siblings (Text, Box).

The bug: mount() didn't create a DOM node for the root fiber, so
_reconcile_children used _attach_new_children_dom (no ordering)
instead of _sync_children_dom (preserves order).
"""
from pyink import Box, Text, component, render_to_string_sync
from pyink.renderer.ansi import strip_ansi


def _render(vnode, columns=40):
    return strip_ansi(render_to_string_sync(vnode, columns=columns))


def _line_of(output, text):
    """Return the line number where text first appears."""
    for i, line in enumerate(output.split("\n")):
        if text in line:
            return i
    return -1


@component
def _Wrapper(children=(), height=3):
    items = list(children) if children else []
    return Box(*items, flex_direction="column", height=height)


def test_component_between_host_elements():
    """@component child should render between its host siblings."""
    tree = Box(
        Text("AAA"),
        _Wrapper(children=[Text("BBB")], height=3),
        Text("CCC"),
        flex_direction="column",
        height=8,
    )
    output = _render(tree)
    a = _line_of(output, "AAA")
    b = _line_of(output, "BBB")
    c = _line_of(output, "CCC")
    assert a < b < c, f"Wrong order: AAA@{a} BBB@{b} CCC@{c}"


def test_multiple_components_interleaved():
    """Multiple @components interleaved with host elements."""
    tree = Box(
        Text("First"),
        _Wrapper(children=[Text("Comp1")], height=2),
        Text("Middle"),
        _Wrapper(children=[Text("Comp2")], height=2),
        Text("Last"),
        flex_direction="column",
        height=12,
    )
    output = _render(tree)
    first = _line_of(output, "First")
    comp1 = _line_of(output, "Comp1")
    middle = _line_of(output, "Middle")
    comp2 = _line_of(output, "Comp2")
    last = _line_of(output, "Last")
    assert first < comp1 < middle < comp2 < last, (
        f"Wrong order: {first} {comp1} {middle} {comp2} {last}"
    )


def test_component_as_first_child():
    """@component as the first child should render at the top."""
    tree = Box(
        _Wrapper(children=[Text("FIRST")], height=2),
        Text("SECOND"),
        flex_direction="column",
        height=5,
    )
    output = _render(tree)
    first = _line_of(output, "FIRST")
    second = _line_of(output, "SECOND")
    assert first < second, f"Wrong order: FIRST@{first} SECOND@{second}"


def test_component_as_last_child():
    """@component as the last child should render at the bottom."""
    tree = Box(
        Text("FIRST"),
        _Wrapper(children=[Text("LAST")], height=2),
        flex_direction="column",
        height=5,
    )
    output = _render(tree)
    first = _line_of(output, "FIRST")
    last = _line_of(output, "LAST")
    assert first < last, f"Wrong order: FIRST@{first} LAST@{last}"


def test_nested_components():
    """Nested @components should render in correct order."""
    @component
    def Inner(label=""):
        return Text(label)

    @component
    def Outer(label=""):
        return Box(Inner(label=label), flex_direction="column")

    tree = Box(
        Text("Before"),
        Outer(label="Nested"),
        Text("After"),
        flex_direction="column",
        height=5,
    )
    output = _render(tree)
    before = _line_of(output, "Before")
    nested = _line_of(output, "Nested")
    after = _line_of(output, "After")
    assert before < nested < after, (
        f"Wrong order: Before@{before} Nested@{nested} After@{after}"
    )
