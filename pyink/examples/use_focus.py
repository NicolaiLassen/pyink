"""Port of Ink's examples/use-focus/use-focus.tsx — Tab focus navigation."""
from pyink import component, render, Box, Text
from pyink.hooks import use_focus


@component
def item(label="Item"):
    focus = use_focus()
    focused_text = Text(" (focused)", color="green") if focus.is_focused else Text("")
    return Text(f"{label}", bold=focus.is_focused)


@component
def focus_demo():
    return Box(
        Box(
            Text("Press Tab to focus next element, Shift+Tab to focus previous."),
            margin_bottom=1,
        ),
        item(label="First"),
        item(label="Second"),
        item(label="Third"),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(focus_demo())
