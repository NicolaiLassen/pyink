"""Port of Ink's examples/use-stdout/use-stdout.tsx."""
from pyink import Box, Text, component, render
from pyink.hooks import use_window_size


@component
def stdout_example():
    size = use_window_size()

    return Box(
        Text("Terminal dimensions:", bold=True, underline=True),
        Box(
            Text("Width: ", color=None),
            Text(str(size.columns), bold=True),
            flex_direction="row",
            margin_top=1,
        ),
        Box(
            Text("Height: "),
            Text(str(size.rows), bold=True),
            flex_direction="row",
        ),
        flex_direction="column",
        padding_x=2,
        padding_y=1,
    )


if __name__ == "__main__":
    render(stdout_example())
