"""Port of Ink's examples/counter/counter.tsx — auto-incrementing counter."""
from pyink import component, render, Text
from pyink.hooks import use_state, use_effect
from pyink.hooks.context import get_current_app


@component
def counter():
    count, set_count = use_state(0)

    # Capture app during render (not in effect)
    app = get_current_app()

    def effect():
        def tick():
            set_count(lambda c: c + 1)

        handle = app.add_timer(0.1, tick, repeating=True)

        def cleanup():
            app.remove_timer(handle)

        return cleanup

    use_effect(effect, ())

    return Text(f"{count} tests passed", color="green")


if __name__ == "__main__":
    render(counter())
