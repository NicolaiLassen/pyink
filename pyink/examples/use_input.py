"""Port of Ink's examples/use-input/use-input.tsx — movable face with arrow keys."""
from pyink import Box, Text, component, render
from pyink.hooks import use_app, use_input, use_state


@component
def robot():
    app = use_app()
    x, set_x = use_state(1)
    y, set_y = use_state(1)

    def handle_input(input_str, key):
        if input_str == "q":
            app.exit()
        if key.left_arrow:
            set_x(lambda v: max(1, v - 1))
        if key.right_arrow:
            set_x(lambda v: min(20, v + 1))
        if key.up_arrow:
            set_y(lambda v: max(1, v - 1))
        if key.down_arrow:
            set_y(lambda v: min(10, v + 1))

    use_input(handle_input)

    return Box(
        Text('Use arrow keys to move the face. Press "q" to exit.'),
        Box(
            Text("^_^"),
            height=12,
            padding_left=x,
            padding_top=y,
        ),
        flex_direction="column",
    )


if __name__ == "__main__":
    render(robot())
