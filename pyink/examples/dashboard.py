"""Multi-panel dashboard example showing flexbox layout."""
from pyink import component, render, Box, Text, Spacer
from pyink.hooks import use_state, use_input, use_app, use_animation


@component
def dashboard():
    app = use_app()
    anim = use_animation(interval=500)

    def handle_input(input_str, key):
        if input_str == "q":
            app.exit()

    use_input(handle_input)

    spinner_chars = ["|", "/", "-", "\\"]
    spinner = spinner_chars[anim.frame % len(spinner_chars)]

    return Box(
        # Header
        Box(
            Text(f" {spinner} PyInk Dashboard ", bold=True, color="white", background_color="blue"),
            justify_content="center",
            width="100%",
        ),
        # Content
        Box(
            # Left panel
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
            # Right panel
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
        # Footer
        Box(
            Text("Press q to quit", dim_color=True),
            justify_content="center",
            margin_top=1,
        ),
        flex_direction="column",
        width="100%",
    )


if __name__ == "__main__":
    render(dashboard())
