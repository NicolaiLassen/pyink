"""Simple hello world example."""
from pyink import Box, Text, component, render
from pyink.hooks import use_app, use_input


@component
def hello():
    app = use_app()

    def handle_input(input_str, key):
        app.exit()

    use_input(handle_input)

    return Box(
        Text("Hello, ", color="green", bold=True),
        Text("World!", color="cyan"),
        flex_direction="row",
        padding=1,
        border_style="round",
    )


if __name__ == "__main__":
    render(hello())
