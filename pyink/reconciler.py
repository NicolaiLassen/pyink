from __future__ import annotations

import asyncio
from typing import Any, Callable

from pyink.dom import (
    DOMElement,
    TextNode,
    append_child,
    create_element,
    create_text_node,
    remove_child,
    squash_text_nodes,
)
from pyink.fiber import Fiber
from pyink.hooks.context import _current_app, _current_fiber, _schedule_update
from pyink.hooks.use_effect import cleanup_effects, run_effects
from pyink.vnode import VNode


class Reconciler:
    """Manages the fiber tree, diffing VNode trees, and scheduling renders."""

    def __init__(self, on_commit: Callable[[], None]) -> None:
        self.root_fiber: Fiber | None = None
        self._dirty_fibers: set[int] = set()  # fiber ids
        self._dirty_fiber_map: dict[int, Fiber] = {}
        self._render_scheduled = False
        self._on_commit = on_commit
        self._app: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_app(self, app: Any) -> None:
        self._app = app

    def mount(self, root_vnode: VNode) -> Fiber:
        """Initial mount of the application."""
        self.root_fiber = self._create_fiber_from_vnode(root_vnode, parent=None)
        self._render_fiber(self.root_fiber)
        self._commit()
        return self.root_fiber

    def schedule_update(self, fiber: Fiber) -> None:
        """Called by set_state. Batches updates via the event loop."""
        fid = id(fiber)
        self._dirty_fibers.add(fid)
        self._dirty_fiber_map[fid] = fiber
        if not self._render_scheduled and self._loop:
            self._render_scheduled = True
            self._loop.call_soon(self._flush_updates)

    def _flush_updates(self) -> None:
        """Process all dirty fibers in a single batch."""
        self._render_scheduled = False
        fibers = [self._dirty_fiber_map[fid] for fid in self._dirty_fibers]
        self._dirty_fibers.clear()
        self._dirty_fiber_map.clear()

        for fiber in fibers:
            self._render_fiber(fiber)

        self._commit()

    def _render_fiber(self, fiber: Fiber) -> None:
        """Execute a component's render function and reconcile children."""
        if not fiber.is_component:
            # Built-in element: reconcile children directly
            self._reconcile_children(fiber, fiber.children_vnodes)
            return

        token = _current_fiber.set(fiber)
        schedule_token = _schedule_update.set(self.schedule_update)
        app_token = _current_app.set(self._app) if self._app else None

        fiber.reset_hook_index()

        try:
            result = fiber.component_fn(**fiber.props)
            if result is None:
                self._reconcile_children(fiber, [])
            elif isinstance(result, VNode):
                self._reconcile_children(fiber, [result])
            elif isinstance(result, list):
                self._reconcile_children(fiber, result)
            else:
                self._reconcile_children(fiber, [str(result)])
        finally:
            _current_fiber.reset(token)
            _schedule_update.reset(schedule_token)
            if app_token is not None:
                _current_app.reset(app_token)

    def _reconcile_children(
        self, fiber: Fiber, new_children: list[VNode | str]
    ) -> None:
        """Diff old child fibers against new VNode children."""
        old_by_key: dict[str, Fiber] = {}
        old_by_pos: dict[int, Fiber] = {}

        for i, old in enumerate(fiber.child_fibers):
            if old.key is not None:
                old_by_key[str(old.key)] = old
            else:
                old_by_pos[i] = old

        new_fibers: list[Fiber] = []
        used_old: set[int] = set()

        for i, child_vnode in enumerate(new_children):
            if isinstance(child_vnode, str):
                # Text node
                old_fiber = old_by_pos.get(i)
                if old_fiber and old_fiber.node_type == "#text":
                    old_fiber.props = {"value": child_vnode}
                    new_fibers.append(old_fiber)
                    used_old.add(id(old_fiber))
                else:
                    tf = Fiber(
                        node_type="#text",
                        props={"value": child_vnode},
                        parent=fiber,
                    )
                    new_fibers.append(tf)
                continue

            if not isinstance(child_vnode, VNode):
                child_vnode = VNode(type="ink-text", children=[str(child_vnode)])

            key = child_vnode.key
            vtype = child_vnode.type

            # Find matching old fiber
            old_fiber = None
            if key is not None and str(key) in old_by_key:
                candidate = old_by_key[str(key)]
                if self._same_type(candidate, vtype):
                    old_fiber = candidate
            elif key is None and i in old_by_pos:
                candidate = old_by_pos[i]
                if self._same_type(candidate, vtype):
                    old_fiber = candidate

            if old_fiber and id(old_fiber) not in used_old:
                # Update existing fiber
                used_old.add(id(old_fiber))
                old_fiber.props = child_vnode.props
                old_fiber.children_vnodes = child_vnode.children
                old_fiber.key = child_vnode.key
                if old_fiber.is_component:
                    self._render_fiber(old_fiber)
                else:
                    self._reconcile_children(old_fiber, child_vnode.children)
                new_fibers.append(old_fiber)
            else:
                # Create new fiber
                new_fiber = self._create_fiber_from_vnode(child_vnode, parent=fiber)
                self._render_fiber(new_fiber)
                new_fibers.append(new_fiber)

        # Destroy remaining old fibers
        for old in fiber.child_fibers:
            if id(old) not in used_old:
                self._destroy_fiber(old)

        fiber.child_fibers = new_fibers

    def _same_type(self, fiber: Fiber, vtype: str | Callable) -> bool:
        if callable(vtype):
            return fiber.component_fn is vtype
        return fiber.node_type == vtype

    def _create_fiber_from_vnode(
        self, vnode: VNode | str, parent: Fiber | None
    ) -> Fiber:
        if isinstance(vnode, str):
            return Fiber(
                node_type="#text", props={"value": vnode}, parent=parent
            )

        if callable(vnode.type):
            return Fiber(
                component_fn=vnode.type,
                props=vnode.props,
                children_vnodes=vnode.children,
                parent=parent,
                key=vnode.key,
            )

        return Fiber(
            node_type=vnode.type,
            props=vnode.props,
            children_vnodes=vnode.children,
            parent=parent,
            key=vnode.key,
        )

    def _destroy_fiber(self, fiber: Fiber) -> None:
        """Cleanup effects and tear down subtree."""
        cleanup_effects(fiber)
        for child in fiber.child_fibers:
            self._destroy_fiber(child)

    def _commit(self) -> None:
        """Build DOM tree from fiber tree and notify renderer."""
        if self.root_fiber:
            root_dom = self._build_dom(self.root_fiber)
            self.root_fiber.dom_node = root_dom
            self._run_all_effects(self.root_fiber)
        self._on_commit()

    def _build_dom(self, fiber: Fiber) -> DOMElement | TextNode | None:
        """Recursively build the DOM tree from the fiber tree."""
        if fiber.node_type == "#text":
            return create_text_node(fiber.props.get("value", ""))

        if fiber.is_component:
            # Components don't produce DOM nodes themselves - use children
            if len(fiber.child_fibers) == 1:
                return self._build_dom(fiber.child_fibers[0])
            elif len(fiber.child_fibers) > 1:
                wrapper = create_element("ink-box")
                for child_fiber in fiber.child_fibers:
                    child_dom = self._build_dom(child_fiber)
                    if child_dom:
                        append_child(wrapper, child_dom)
                return wrapper
            return None

        # Built-in element
        el = create_element(fiber.node_type or "ink-box")
        el.style = dict(fiber.props)
        # Remove non-style props
        for key in ("_static", "children"):
            el.style.pop(key, None)

        for child_fiber in fiber.child_fibers:
            child_dom = self._build_dom(child_fiber)
            if child_dom:
                append_child(el, child_dom)

        fiber.dom_node = el
        return el

    def _run_all_effects(self, fiber: Fiber) -> None:
        run_effects(fiber)
        for child in fiber.child_fibers:
            self._run_all_effects(child)

    def unmount(self) -> None:
        if self.root_fiber:
            self._destroy_fiber(self.root_fiber)
            self.root_fiber = None
