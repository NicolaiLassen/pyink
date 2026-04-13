"""Tests for border rendering."""
from pyink import component, Box, Text, render_to_string_sync
from pyink.renderer.ansi import strip_ansi
from pyink.renderer.borders import BORDER_STYLES


def test_all_border_styles():
    for style_name in BORDER_STYLES:
        @component
        def app():
            return Box(
                Text("test"),
                border_style=style_name,
                width=10,
                height=3,
            )

        output = render_to_string_sync(app(), columns=20)
        clean = strip_ansi(output)
        assert len(clean) > 0, f"Style '{style_name}' produced no output"


def test_round_border_chars():
    @component
    def app():
        return Box(Text("x"), border_style="round", width=5, height=3)

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    assert "╭" in clean
    assert "╰" in clean
    assert "╮" in clean
    assert "╯" in clean


def test_border_with_color():
    @component
    def app():
        return Box(
            Text("x"),
            border_style="single",
            border_color="red",
            width=10,
            height=3,
        )

    output = render_to_string_sync(app(), columns=20)
    assert "\x1b[31m" in output  # red color


def test_border_visibility():
    @component
    def app():
        return Box(
            Text("x"),
            border_style="single",
            border_top=False,
            width=10,
            height=3,
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    lines = clean.split("\n")
    # First line should not have top border
    assert "┌" not in lines[0]


def test_per_edge_border_colors():
    @component
    def app():
        return Box(
            Text("x"),
            border_style="single",
            border_top_color="red",
            border_bottom_color="green",
            width=10,
            height=3,
        )

    output = render_to_string_sync(app(), columns=20)
    assert "\x1b[31m" in output  # red
    assert "\x1b[32m" in output  # green
