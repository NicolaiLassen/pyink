from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EffectRecord:
    setup: Callable
    cleanup: Callable | None = None
    deps: tuple | None = None
    prev_deps: tuple | None = None


@dataclass
class Ref:
    current: Any = None


@dataclass
class Fiber:
    """A living instance of a component in the tree. Analogous to React Fiber.

    Each Fiber holds the hook state for one component instance and
    links to its children in the fiber tree.
    """

    component_fn: Callable | None = None
    node_type: str | None = None  # for built-in elements: "ink-box", "ink-text"
    props: dict[str, Any] = field(default_factory=dict)
    children_vnodes: list = field(default_factory=list)

    # Hook state - indexed by call order
    hook_state: list[Any] = field(default_factory=list)
    hook_index: int = 0

    # Effects
    effects: list[EffectRecord] = field(default_factory=list)
    effect_index: int = 0

    # Layout effects (run synchronously during commit, before render)
    layout_effects: list[EffectRecord] = field(default_factory=list)
    layout_effect_index: int = 0

    # Tree links
    child_fibers: list[Fiber] = field(default_factory=list)
    parent: Fiber | None = None

    # DOM node reference (set during commit phase)
    dom_node: Any = None

    # Reconciliation key
    key: str | int | None = None

    @property
    def is_component(self) -> bool:
        return self.component_fn is not None

    def reset_hook_index(self) -> None:
        self.hook_index = 0
        self.effect_index = 0
        self.layout_effect_index = 0
