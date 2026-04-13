"""Port of Ink's examples/justify-content/justify-content.tsx."""
from pyink import Box, Text, component, render


@component
def justify_content():
    modes = [
        "flex-start", "flex-end", "center",
        "space-around", "space-between", "space-evenly",
    ]

    rows = []
    for mode in modes:
        rows.append(
            Box(
                Text("["),
                Box(
                    Text("X"),
                    Text("Y"),
                    justify_content=mode,
                    width=20,
                    height=1,
                    flex_direction="row",
                ),
                Text(f"] {mode}"),
                flex_direction="row",
            )
        )

    return Box(*rows, flex_direction="column")


if __name__ == "__main__":
    render(justify_content())
