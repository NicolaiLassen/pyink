"""Port of Ink's examples/chat/chat.tsx — simple chat input."""
from pyink import Box, Text, component, render
from pyink.hooks import use_input, use_state

message_id = 0


@component
def chat_app():
    global message_id
    input_text, set_input = use_state("")
    messages, set_messages = use_state([])

    def handle_input(ch, key):
        global message_id
        if key.return_key:
            if input_text:
                new_msg = {"id": message_id, "text": f"User: {input_text}"}
                message_id += 1
                set_messages(lambda prev: prev + [new_msg])
                set_input("")
        elif key.backspace or key.delete:
            set_input(lambda t: t[:-1])
        else:
            if ch and not key.ctrl and not key.meta:
                set_input(lambda t: t + ch)

    use_input(handle_input)

    msg_rows = [Text(m["text"]) for m in messages]

    return Box(
        Box(*msg_rows, flex_direction="column") if msg_rows else Text(""),
        Box(
            Text(f"Enter your message: {input_text}"),
            margin_top=1,
        ),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(chat_app())
