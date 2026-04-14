from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from pyink.vnode import VNode


def component(fn: Callable) -> Callable[..., VNode]:
    """Decorator that turns a function into a pyink component.

    The decorated function, when called, does NOT execute the body.
    Instead it returns a VNode whose type is the original function.
    The reconciler calls the body later when processing the VNode.

    Parameters
    ----------
    fn : Callable
        The render function to wrap as a component.

    Returns
    -------
    Callable[..., VNode]
        A wrapper that produces a VNode when called with children and props.
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
