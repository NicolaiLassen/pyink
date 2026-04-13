"""Port of Ink's examples/table/table.tsx — data table with columns."""
import random
from pyink import component, render, Box, Text


def random_username():
    prefixes = ["cool", "super", "mega", "ultra", "hyper", "neo", "cyber"]
    suffixes = ["dev", "coder", "hacker", "ninja", "guru", "wizard", "pro"]
    return f"{random.choice(prefixes)}_{random.choice(suffixes)}{random.randint(1, 99)}"


def random_email(name):
    domains = ["gmail.com", "outlook.com", "dev.io", "code.org"]
    return f"{name}@{random.choice(domains)}"


USERS = []
for i in range(10):
    name = random_username()
    USERS.append({"id": i, "name": name, "email": random_email(name)})


@component
def table():
    rows = [
        Box(
            Box(Text("ID"), width="10%"),
            Box(Text("Name"), width="50%"),
            Box(Text("Email"), width="40%"),
            flex_direction="row",
        )
    ]

    for user in USERS:
        rows.append(
            Box(
                Box(Text(str(user["id"])), width="10%"),
                Box(Text(user["name"]), width="50%"),
                Box(Text(user["email"]), width="40%"),
                flex_direction="row",
                key=user["id"],
            )
        )

    return Box(*rows, flex_direction="column", width=80)


if __name__ == "__main__":
    render(table())
