"""Focus management example with visual indicators."""
from pyink import component, render, Box, Text
from pyink.hooks import use_state, use_input, use_app, use_focus


@component
def focusable_item(label="Item"):
    focus = use_focus()
    color = "green" if focus.is_focused else "gray"
    indicator = ">" if focus.is_focused else " "

    return Box(
        Text(f" {indicator} {label} ", color=color, bold=focus.is_focused),
        border_style="round" if focus.is_focused else "single",
        border_color=color,
    )


@component
def focus_demo():
    app = use_app()

    def handle_input(input_str, key):
        if input_str == "q":
            app.exit()

    use_input(handle_input)

    return Box(
        Text("Tab Navigation Demo", bold=True, color="cyan"),
        Box(
            focusable_item(label="First Item"),
            focusable_item(label="Second Item"),
            focusable_item(label="Third Item"),
            flex_direction="column",
            gap=1,
            margin_top=1,
        ),
        Box(
            Text("Tab/Shift+Tab to navigate, q to quit", dim_color=True),
            margin_top=1,
        ),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(focus_demo())
