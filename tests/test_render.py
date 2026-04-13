"""Tests for the rendering pipeline."""
from pyink import component, Box, Text, Spacer, Newline, Transform, render_to_string_sync
from pyink.renderer.ansi import strip_ansi


def test_simple_text():
    @component
    def app():
        return Text("Hello")

    output = render_to_string_sync(app(), columns=20)
    assert "Hello" in strip_ansi(output)


def test_box_with_padding():
    @component
    def app():
        return Box(Text("Hi"), padding=1, border_style="single")

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    assert "┌" in clean  # top-left border
    assert "Hi" in clean


def test_flex_row():
    @component
    def app():
        return Box(
            Text("A"),
            Text("B"),
            flex_direction="row",
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    a_pos = clean.find("A")
    b_pos = clean.find("B")
    # In row layout, B should be to the right of A
    assert a_pos < b_pos


def test_flex_column():
    @component
    def app():
        return Box(
            Text("Line1"),
            Text("Line2"),
            flex_direction="column",
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    lines = clean.split("\n")
    line1_row = next(i for i, l in enumerate(lines) if "Line1" in l)
    line2_row = next(i for i, l in enumerate(lines) if "Line2" in l)
    assert line2_row > line1_row


def test_spacer():
    @component
    def app():
        return Box(
            Text("L"),
            Spacer(),
            Text("R"),
            flex_direction="row",
        )

    output = render_to_string_sync(app(), columns=40)
    clean = strip_ansi(output)
    # L should be near start, R near end
    assert clean.index("L") < clean.index("R")
    assert clean.index("R") > 10  # R should be pushed right


def test_text_colors():
    @component
    def app():
        return Text("colored", color="red")

    output = render_to_string_sync(app(), columns=20)
    assert "\x1b[31m" in output  # red color code
    assert "colored" in output


def test_text_bold():
    @component
    def app():
        return Text("strong", bold=True)

    output = render_to_string_sync(app(), columns=20)
    assert "\x1b[1m" in output  # bold code


def test_border_styles():
    for style in ["single", "double", "round", "bold", "classic"]:
        @component
        def app():
            return Box(Text("x"), border_style=style)

        output = render_to_string_sync(app(), columns=20)
        clean = strip_ansi(output)
        assert len(clean) > 0, f"Border style '{style}' produced empty output"


def test_transform():
    @component
    def app():
        return Transform(
            Text("hello"),
            transform=lambda text, idx: text.upper(),
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    assert "HELLO" in clean


def test_newline():
    @component
    def app():
        return Box(
            Text("Before"),
            Newline(),
            Text("After"),
            flex_direction="column",
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    assert "Before" in clean
    assert "After" in clean


def test_nested_boxes():
    @component
    def app():
        return Box(
            Box(Text("inner"), border_style="single", padding=1),
            padding=1,
            border_style="round",
        )

    output = render_to_string_sync(app(), columns=40)
    clean = strip_ansi(output)
    # Should have both round (outer) and single (inner) borders
    assert "╭" in clean  # round
    assert "┌" in clean  # single


def test_margin():
    @component
    def app():
        return Box(
            Box(
                Text("text"),
                margin_top=2,
            ),
            flex_direction="column",
            height=5,
        )

    output = render_to_string_sync(app(), columns=20)
    clean = strip_ansi(output)
    lines = clean.split("\n")
    # First non-empty line with text should be after margin
    first_content = next(i for i, l in enumerate(lines) if "text" in l)
    assert first_content >= 2
