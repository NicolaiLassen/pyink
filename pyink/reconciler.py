"""Fiber-based reconciler — diffs VNode trees, schedules renders.

1:1 port of Ink's reconciler patterns from ``src/reconciler.ts``.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pyink.dom import (
    DOMElement,
    TextNode,
    append_child,
    create_node,
    create_text_node,
    set_attribute,
    set_style,
)
from pyink.fiber import Fiber
from pyink.hooks.context import _current_app, _current_fiber, _schedule_update
from pyink.hooks.use_effect import cleanup_effects, run_effects
from pyink.layout.styles import apply_styles
from pyink.vnode import VNode

# Props that are NOT yoga/style props — they get special handling
_SPECIAL_PROPS = frozenset(
    {"children", "key", "style", "internal_transform", "internal_static"}
)


def _diff(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Compute changed props between two dicts.

    Port of Ink's ``diff`` (reconciler.ts lines 48–79).

    Parameters
    ----------
    before : dict or None
        Previous props.
    after : dict or None
        New props.

    Returns
    -------
    dict or None
        Dict of changed keys, or None if unchanged.
    """
    if before is after:
        return None

    if not before:
        return after

    changed: dict[str, Any] = {}
    is_changed = False

    for key in before:
        if after is None or key not in after:
            changed[key] = None
            is_changed = True

    if after:
        for key in after:
            if after[key] is not before.get(key):
                changed[key] = after[key]
                is_changed = True

    return changed if is_changed else None


def _cleanup_yoga_node(node: DOMElement) -> None:
    """Free yoga node resources.

    Port of Ink's ``cleanupYogaNode`` (reconciler.ts lines 81–84).

    Parameters
    ----------
    node : DOMElement
        The element whose yoga node should be freed.
    """
    if node.yoga_node is not None:
        try:
            node.yoga_node.free()
        except Exception:
            pass


class Reconciler:
    """Manages the fiber tree, diffing VNode trees, and scheduling renders.

    Parameters
    ----------
    on_commit : Callable[[], None]
        Callback invoked after each commit so the renderer can
        repaint.
    """

    def __init__(self, on_commit: Callable[[], None]) -> None:
        self.root_fiber: Fiber | None = None
        self._dirty_fibers: set[int] = set()  # fiber ids
        self._dirty_fiber_map: dict[int, Fiber] = {}
        self._render_scheduled = False
        self._on_commit = on_commit
        self._app: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._root_node: DOMElement | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Assign the event loop used for scheduling batched updates.

        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The running event loop.
        """
        self._loop = loop

    def set_app(self, app: Any) -> None:
        """Assign the application instance used as context for hooks.

        Parameters
        ----------
        app : Any
            The ``App`` instance.
        """
        self._app = app

    def mount(self, root_vnode: VNode) -> Fiber:
        """Initial mount of the application.

        Parameters
        ----------
        root_vnode : VNode
            The root virtual node to mount.

        Returns
        -------
        Fiber
            The root fiber of the mounted tree.
        """
        self.root_fiber = self._create_fiber_from_vnode(root_vnode, parent=None)
        self._render_fiber(self.root_fiber)
        self._commit()
        return self.root_fiber

    def schedule_update(self, fiber: Fiber) -> None:
        """Called by set_state. Batches updates via the event loop.

        Uses call_soon_threadsafe so background threads can trigger
        re-renders (e.g. streaming responses).

        Parameters
        ----------
        fiber : Fiber
            The fiber whose state has changed and needs re-rendering.
        """
        fid = id(fiber)
        self._dirty_fibers.add(fid)
        self._dirty_fiber_map[fid] = fiber
        if not self._render_scheduled and self._loop:
            self._render_scheduled = True
            try:
                self._loop.call_soon_threadsafe(self._flush_updates)
            except RuntimeError:
                self._render_scheduled = False

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
        except Exception:
            # Port of ErrorBoundary: catch render errors and exit app
            # (Ink components/ErrorBoundary.tsx)
            import sys
            import traceback

            traceback.print_exc(file=sys.stderr)
            if self._app and hasattr(self._app, "request_exit"):
                self._app.request_exit(1)
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
        # Cleanup yoga nodes on DOM elements
        if fiber.dom_node and isinstance(fiber.dom_node, DOMElement):
            _cleanup_yoga_node(fiber.dom_node)
        for child in fiber.child_fibers:
            self._destroy_fiber(child)

    def _commit(self) -> None:
        """Build DOM tree from fiber tree and notify renderer.

        Port of Ink's resetAfterCommit (reconciler.ts lines 160–182).
        Since pyink rebuilds the DOM each commit (middle-ground approach),
        we delegate layout/render scheduling to the App via ``_on_commit``.
        """
        if self.root_fiber:
            root_dom = self._build_dom(self.root_fiber, is_inside_text=False)
            self.root_fiber.dom_node = root_dom
            self._root_node = root_dom if isinstance(root_dom, DOMElement) else None

            # Wire up static_node after root_dom exists.
            if isinstance(root_dom, DOMElement):
                self._wire_static_node(root_dom)

            self._run_all_effects(self.root_fiber)
        self._on_commit()

    def _wire_static_node(self, root_dom: DOMElement) -> None:
        """Find internal_static child and assign it to root_dom.static_node.

        Port of Ink's reconciler pattern for <Static> node tracking.
        Uses ``internal_static`` field instead of style prop.
        """
        for child in root_dom.children:
            if isinstance(child, DOMElement) and child.internal_static:
                old = root_dom.static_node
                root_dom.static_node = child
                # Mark dirty when node is new or has different child count
                if old is None or len(child.children) != len(
                    getattr(old, "children", [])
                ):
                    root_dom.is_static_dirty = True
                return

    def _build_dom(
        self, fiber: Fiber, is_inside_text: bool = False
    ) -> DOMElement | TextNode | None:
        """Recursively build the DOM tree from the fiber tree.

        Port of Ink's ``createInstance`` + ``commitUpdate`` patterns.

        Parameters
        ----------
        fiber : Fiber
            The fiber to build DOM for.
        is_inside_text : bool
            Whether we're inside an ink-text element. Text nested
            in text becomes ink-virtual-text (reconciler.ts lines 183–201).
        """
        if fiber.node_type == "#text":
            if not is_inside_text:
                raise ValueError(
                    f'Text string "{fiber.props.get("value", "")}" '
                    "must be rendered inside <Text> component"
                )
            return create_text_node(fiber.props.get("value", ""))

        if fiber.is_component:
            # Components don't produce DOM nodes themselves — use children
            if len(fiber.child_fibers) == 1:
                return self._build_dom(fiber.child_fibers[0], is_inside_text)
            elif len(fiber.child_fibers) > 1:
                wrapper = create_node("ink-box")
                for child_fiber in fiber.child_fibers:
                    child_dom = self._build_dom(child_fiber, is_inside_text)
                    if child_dom:
                        append_child(wrapper, child_dom)
                return wrapper
            return None

        # Built-in element — port of reconciler.ts createInstance
        node_type = fiber.node_type or "ink-box"

        # isInsideText tracking (reconciler.ts lines 194–201)
        if is_inside_text and node_type == "ink-box":
            raise ValueError("<Box> can't be nested inside <Text> component")

        if node_type == "ink-text" and is_inside_text:
            node_type = "ink-virtual-text"

        el = create_node(node_type)

        # Apply props — port of reconciler.ts createInstance lines 206–238
        props = fiber.props
        style_props: dict[str, Any] = {}
        accessibility: dict[str, Any] = {}

        for key, value in props.items():
            if key == "children":
                continue

            if key == "internal_transform":
                el.internal_transform = value
                continue

            if key == "internal_static":
                el.internal_static = True
                if self._root_node:
                    self._root_node.is_static_dirty = True
                    self._root_node.static_node = el
                continue

            if key == "internal_accessibility":
                set_attribute(el, key, value)
                continue

            # ARIA props → internal_accessibility (Box.tsx/Text.tsx)
            if key in ("aria_label", "aria_hidden", "aria_role", "aria_state"):
                aria_key = key[5:]  # strip "aria_" prefix
                accessibility[aria_key] = value
                continue

            if key == "key":
                continue

            # Everything else goes into style
            style_props[key] = value

        # Apply collected ARIA props
        if accessibility:
            set_attribute(el, "internal_accessibility", accessibility)

        set_style(el, style_props)
        if el.yoga_node:
            apply_styles(el.yoga_node, style_props)

        # Determine child isInsideText context
        child_is_inside_text = is_inside_text or node_type in (
            "ink-text",
            "ink-virtual-text",
        )

        for child_fiber in fiber.child_fibers:
            child_dom = self._build_dom(child_fiber, child_is_inside_text)
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
