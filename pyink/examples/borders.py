"""Port of Ink's examples/borders/borders.tsx — all border styles."""
from pyink import component, render, Box, Text


@component
def borders_demo():
    return Box(
        Box(
            Box(Text("single"), border_style="single", margin_right=2),
            Box(Text("double"), border_style="double", margin_right=2),
            Box(Text("round"), border_style="round", margin_right=2),
            Box(Text("bold"), border_style="bold"),
            flex_direction="row",
        ),
        Box(
            Box(Text("single-double"), border_style="single-double", margin_right=2),
            Box(Text("double-single"), border_style="double-single", margin_right=2),
            Box(Text("classic"), border_style="classic"),
            flex_direction="row",
            margin_top=1,
        ),
        flex_direction="column",
        padding=2,
    )


if __name__ == "__main__":
    render(borders_demo())
