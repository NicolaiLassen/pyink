"""Port of Ink's examples/terminal-resize/terminal-resize.tsx."""
from pyink import Box, Text, component, render
from pyink.hooks import use_window_size


@component
def terminal_resize():
    size = use_window_size()

    return Box(
        Text("Terminal Size", bold=True, color="cyan"),
        Text(f"Columns: {size.columns}"),
        Text(f"Rows: {size.rows}"),
        Box(
            Text("Resize your terminal to see values update. Ctrl+C to exit.", dim_color=True),
            margin_top=1,
        ),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(terminal_resize())
