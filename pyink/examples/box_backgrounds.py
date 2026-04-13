"""Port of Ink's examples/box-backgrounds/box-backgrounds.tsx."""
from pyink import Box, Text, component, render


@component
def box_backgrounds():
    return Box(
        Text("Box Background Examples:", bold=True),
        Text("1. Red background (10x3):"),
        Box(Text("Hello"), background_color="red", width=10, height=3),
        Text("2. Blue background with border (12x4):"),
        Box(Text("Border"), background_color="blue", border_style="round", width=12, height=4),
        Text("3. Green background with padding (14x4):"),
        Box(Text("Padding"), background_color="green", padding=1, width=14, height=4),
        Text("4. Hex color background #FF8800 (10x3):"),
        Box(Text("Hex"), background_color="#FF8800", width=10, height=3),
        flex_direction="column",
        gap=1,
    )


if __name__ == "__main__":
    render(box_backgrounds())
