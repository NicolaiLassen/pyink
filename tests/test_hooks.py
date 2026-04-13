"""Tests for hooks system."""
from pyink import component, Box, Text, render_to_string_sync
from pyink.hooks import use_state, use_ref, use_memo, use_callback, use_effect
from pyink.renderer.ansi import strip_ansi


def test_use_state_initial_value():
    @component
    def app():
        count, set_count = use_state(42)
        return Text(f"Count: {count}")

    output = render_to_string_sync(app(), columns=20)
    assert "Count: 42" in strip_ansi(output)


def test_use_state_with_different_types():
    @component
    def app():
        text, _ = use_state("hello")
        num, _ = use_state(3.14)
        lst, _ = use_state([1, 2, 3])
        return Box(
            Text(f"{text} {num} {len(lst)}"),
        )

    output = render_to_string_sync(app(), columns=40)
    clean = strip_ansi(output)
    assert "hello" in clean
    assert "3.14" in clean
    assert "3" in clean


def test_use_ref():
    @component
    def app():
        ref = use_ref("initial")
        return Text(f"Ref: {ref.current}")

    output = render_to_string_sync(app(), columns=20)
    assert "Ref: initial" in strip_ansi(output)


def test_use_memo():
    call_count = [0]

    @component
    def app():
        def factory():
            call_count[0] += 1
            return "computed"

        value = use_memo(factory, ("dep1",))
        return Text(f"Value: {value}")

    output = render_to_string_sync(app(), columns=30)
    assert "Value: computed" in strip_ansi(output)
    assert call_count[0] == 1


def test_multiple_hooks():
    @component
    def app():
        a, _ = use_state("A")
        b, _ = use_state("B")
        c, _ = use_state("C")
        return Text(f"{a}{b}{c}")

    output = render_to_string_sync(app(), columns=20)
    assert "ABC" in strip_ansi(output)


def test_nested_components_with_state():
    @component
    def child(value="default"):
        count, _ = use_state(0)
        return Text(f"{value}:{count}")

    @component
    def parent():
        return Box(
            child(value="first"),
            child(value="second"),
            flex_direction="column",
        )

    output = render_to_string_sync(parent(), columns=20)
    clean = strip_ansi(output)
    assert "first:0" in clean
    assert "second:0" in clean
