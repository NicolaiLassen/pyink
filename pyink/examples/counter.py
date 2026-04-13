"""Interactive counter example matching Ink's counter demo."""
from pyink import component, render, Box, Text
from pyink.hooks import use_state, use_input, use_app


@component
def counter():
    count, set_count = use_state(0)
    app = use_app()

    def handle_input(input_str, key):
        if key.up_arrow:
            set_count(lambda c: c + 1)
        elif key.down_arrow:
            set_count(lambda c: max(0, c - 1))
        elif input_str == "q":
            app.exit()

    use_input(handle_input)

    return Box(
        Text(f"Counter: {count}", color="cyan", bold=True),
        Box(
            Text("Up/Down arrows to change, q to quit", dim_color=True),
            margin_top=1,
        ),
        flex_direction="column",
        padding=1,
        border_style="round",
    )


if __name__ == "__main__":
    render(counter())
