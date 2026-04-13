"""Port of Ink's examples/border-backgrounds/border-backgrounds.tsx."""
from pyink import Box, Text, component, render


@component
def border_backgrounds():
    return Box(
        Box(
            Text("Box with blue background on white border"),
            border_style="round",
            border_color="white",
            border_background_color="blue",
            padding=1,
        ),
        Box(
            Text("Box with yellow background on black border"),
            border_style="single",
            border_color="black",
            border_background_color="yellow",
            padding=1,
        ),
        Box(
            Text("Box with different colors per side"),
            border_style="double",
            border_top_color="red",
            border_top_background_color="green",
            border_bottom_color="blue",
            border_bottom_background_color="yellow",
            border_left_color="cyan",
            border_left_background_color="magenta",
            border_right_color="white",
            border_right_background_color="red",
            padding=1,
        ),
        Box(
            Text("Box with hex color backgrounds"),
            border_style="bold",
            border_color="#FF00FF",
            border_background_color="#00FF00",
            padding=1,
        ),
        flex_direction="column",
        gap=1,
    )


if __name__ == "__main__":
    render(border_backgrounds())
