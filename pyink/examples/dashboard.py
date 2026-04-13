"""Multi-panel dashboard with animation."""
from pyink import component, render, Box, Text, Spacer
from pyink.hooks import use_state, use_input, use_app, use_animation

SPINNER = ["|", "/", "-", "\\"]


@component
def dashboard():
    app = use_app()
    anim = use_animation(interval=500)

    def handle_input(input_str, key):
        if input_str == "q":
            app.exit()

    use_input(handle_input)

    spinner = SPINNER[anim.frame % len(SPINNER)]

    return Box(
        Box(
            Text(f" {spinner} PyInk Dashboard ", bold=True, inverse=True),
            justify_content="center",
        ),
        Box(
            Box(
                Text("System Status", bold=True, color="green"),
                Text("CPU: 45%"),
                Text("Memory: 2.1GB / 8GB"),
                Text("Disk: 120GB / 500GB"),
                flex_direction="column",
                flex_grow=1,
                border_style="single",
                border_color="green",
                padding=1,
            ),
            Box(
                Text("Recent Activity", bold=True, color="yellow"),
                Text("12:00 - Deploy v2.1.0"),
                Text("11:45 - Tests passed"),
                Text("11:30 - PR #42 merged"),
                flex_direction="column",
                flex_grow=2,
                border_style="single",
                border_color="yellow",
                padding=1,
            ),
            flex_direction="row",
            margin_top=1,
        ),
        Box(
            Text("Press q to quit", dim_color=True),
            justify_content="center",
            margin_top=1,
        ),
        flex_direction="column",
    )


if __name__ == "__main__":
    render(dashboard())
