from __future__ import annotations

import functools
from typing import Any, Callable

from pyink.vnode import VNode


def component(fn: Callable) -> Callable[..., VNode]:
    """Decorator that turns a function into a pyink component.

    The decorated function, when called, does NOT execute the body.
    Instead it returns a VNode whose type is the original function.
    The reconciler calls the body later when processing the VNode.
    """

    @functools.wraps(fn)
    def wrapper(*children: VNode | str, **props: Any) -> VNode:
        key = props.pop("key", None)
        return VNode(
            type=fn,
            props=props,
            children=list(children),
            key=key,
        )

    wrapper._is_component = True  # type: ignore[attr-defined]
    wrapper._original_fn = fn  # type: ignore[attr-defined]
    return wrapper
