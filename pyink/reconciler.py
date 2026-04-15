"""Fiber-based reconciler with in-place DOM mutation.

Port of Ink's reconciler (``src/reconciler.ts``). DOM nodes are created
during fiber reconciliation and mutated in place — never rebuilt from scratch.
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
    insert_before,
    remove_child,
    set_attribute,
    set_style,
    set_text_node_value,
)
from pyink.fiber import Fiber
from pyink.hooks.context import _current_app, _current_fiber, _schedule_update
from pyink.hooks.use_effect import cleanup_effects, run_effects, run_layout_effects
from pyink.layout.styles import apply_styles
from pyink.vnode import VNode


def _diff(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Compute changed props between two dicts.

    Port of Ink's ``diff`` (reconciler.ts lines 48–79).
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
    """Free yoga node resources. Port of cleanupYogaNode."""
    if node.yoga_node is not None:
        try:
            node.yoga_node.free()
        except Exception:
            pass


class Reconciler:
    """In-place DOM mutation reconciler matching Ink's architecture.

    DOM nodes are created alongside fibers and mutated in place when
    props change. ``_build_dom`` is gone — the DOM tree is always live.
    """

    def __init__(self, on_commit: Callable[[], None]) -> None:
        self.root_fiber: Fiber | None = None
        self._dirty_fibers: set[int] = set()
        self._dirty_fiber_map: dict[int, Fiber] = {}
        self._render_scheduled = False
        self._on_commit = on_commit
        self._app: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Persistent root DOM node — lives for the app's lifetime
        self._root_node: DOMElement = create_node("ink-root")

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Assign the event loop used for scheduling batched updates."""
        self._loop = loop

    def set_app(self, app: Any) -> None:
        """Assign the App instance used as context for hooks."""
        self._app = app

    # ── Mount ──

    def mount(self, root_vnode: VNode) -> Fiber:
        """Initial mount. Creates the fiber tree and populates the root DOM."""
        self.root_fiber = self._create_fiber_from_vnode(root_vnode, parent=None)
        self._render_fiber(self.root_fiber, is_inside_text=False)
        self._commit()
        return self.root_fiber

    # ── Updates ──

    def schedule_update(self, fiber: Fiber) -> None:
        """Called by set_state. Batches updates via the event loop."""
        if self._loop is None or self._loop.is_closed():
            return
        fid = id(fiber)
        self._dirty_fibers.add(fid)
        self._dirty_fiber_map[fid] = fiber
        if not self._render_scheduled:
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

        # If layout effects already flushed these updates, nothing to do.
        if not fibers:
            return

        try:
            for fiber in fibers:
                self._render_fiber(fiber, is_inside_text=self._is_fiber_inside_text(fiber))

            self._commit()
        except Exception:
            import sys
            import traceback

            traceback.print_exc(file=sys.stderr)

    # ── Render + Reconcile ──

    def _render_fiber(self, fiber: Fiber, is_inside_text: bool) -> None:
        """Execute a component's render function and reconcile children."""
        if not fiber.is_component:
            self._reconcile_children(fiber, fiber.children_vnodes, is_inside_text)
            return

        token = _current_fiber.set(fiber)
        schedule_token = _schedule_update.set(self.schedule_update)
        app_token = _current_app.set(self._app) if self._app else None

        fiber.reset_hook_index()

        try:
            result = fiber.component_fn(**fiber.props)
            if result is None:
                self._reconcile_children(fiber, [], is_inside_text)
            elif isinstance(result, VNode):
                self._reconcile_children(fiber, [result], is_inside_text)
            elif isinstance(result, list):
                self._reconcile_children(fiber, result, is_inside_text)
            else:
                self._reconcile_children(fiber, [str(result)], is_inside_text)
        except Exception:
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
        self, fiber: Fiber, new_children: list[VNode | str], is_inside_text: bool
    ) -> None:
        """Diff old child fibers against new VNode children.

        This is where in-place DOM mutation happens:
        - Reused fibers get their DOM nodes updated via _update_dom_node
        - New fibers get DOM nodes created via _create_dom_node
        - Removed fibers get their DOM nodes detached
        - Child DOM order is synced after reconciliation
        """
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
                    # Reuse — update text in place (commitTextUpdate)
                    used_old.add(id(old_fiber))
                    old_value = old_fiber.props.get("value", "")
                    new_value = child_vnode
                    old_fiber.props = {"value": new_value}
                    if old_value != new_value and isinstance(old_fiber.dom_node, TextNode):
                        set_text_node_value(old_fiber.dom_node, new_value)
                    new_fibers.append(old_fiber)
                else:
                    # New text fiber
                    tf = Fiber(
                        node_type="#text",
                        props={"value": child_vnode},
                        parent=fiber,
                    )
                    self._create_dom_node(tf, is_inside_text=True)
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
                # ── Reuse existing fiber — MUTATE DOM in place ──
                used_old.add(id(old_fiber))
                old_props = dict(old_fiber.props)
                old_fiber.props = child_vnode.props
                old_fiber.children_vnodes = child_vnode.children
                old_fiber.key = child_vnode.key

                # commitUpdate: mutate existing DOM node
                if old_fiber.dom_node and isinstance(old_fiber.dom_node, DOMElement):
                    self._update_dom_node(old_fiber, old_props, child_vnode.props)

                # Determine child context
                child_inside_text = is_inside_text
                if old_fiber.node_type in ("ink-text", "ink-virtual-text"):
                    child_inside_text = True

                if old_fiber.is_component:
                    self._render_fiber(old_fiber, child_inside_text)
                else:
                    self._reconcile_children(old_fiber, child_vnode.children, child_inside_text)
                new_fibers.append(old_fiber)
            else:
                # ── New fiber — CREATE DOM node ──
                new_fiber = self._create_fiber_from_vnode(child_vnode, parent=fiber)

                # Determine child context
                child_inside_text = is_inside_text
                nt = new_fiber.node_type
                if nt in ("ink-text", "ink-virtual-text"):
                    child_inside_text = True
                elif nt == "ink-text" and is_inside_text:
                    child_inside_text = True

                if not new_fiber.is_component:
                    self._create_dom_node(new_fiber, is_inside_text)

                self._render_fiber(new_fiber, child_inside_text)
                new_fibers.append(new_fiber)

        # Destroy removed fibers (detaches their DOM nodes)
        for old in fiber.child_fibers:
            if id(old) not in used_old:
                self._destroy_fiber(old)

        fiber.child_fibers = new_fibers

        # Wire new DOM nodes into the tree.
        # For host fibers: sync DOM children to match fiber children.
        # For component fibers: attach newly created children's DOM nodes
        # to the nearest ancestor host DOM (without removing siblings).
        if fiber.dom_node is not None:
            self._sync_children_dom(fiber)
        else:
            # Component fiber: just ensure new children are attached
            self._attach_new_children_dom(fiber)

    # ── DOM Creation (port of createInstance/createTextInstance) ──

    def _create_dom_node(
        self, fiber: Fiber, is_inside_text: bool
    ) -> DOMElement | TextNode | None:
        """Create a DOM node for a built-in element fiber."""
        if fiber.node_type == "#text":
            if not is_inside_text:
                # Text outside <Text> — Ink raises, we silently create
                pass
            node = create_text_node(fiber.props.get("value", ""))
            fiber.dom_node = node
            return node

        if fiber.is_component:
            return None

        node_type = fiber.node_type or "ink-box"

        # isInsideText tracking (reconciler.ts lines 194–201)
        if is_inside_text and node_type == "ink-box":
            raise ValueError("<Box> can't be nested inside <Text> component")
        if node_type == "ink-text" and is_inside_text:
            node_type = "ink-virtual-text"

        el = create_node(node_type)
        self._apply_props_to_node(el, fiber.props)
        fiber.dom_node = el
        return el

    def _apply_props_to_node(self, el: DOMElement, props: dict[str, Any]) -> None:
        """Apply all props to a new DOM node. Port of createInstance loop."""
        style_props: dict[str, Any] = {}
        accessibility: dict[str, Any] = {}

        for key, value in props.items():
            if key == "children":
                continue
            if key == "key":
                continue

            if key == "internal_transform":
                el.internal_transform = value
                continue

            if key == "internal_static":
                el.internal_static = True
                self._root_node.is_static_dirty = True
                self._root_node.static_node = el
                continue

            if key == "internal_accessibility":
                set_attribute(el, key, value)
                continue

            if key in ("aria_label", "aria_hidden", "aria_role", "aria_state"):
                accessibility[key[5:]] = value
                continue

            style_props[key] = value

        if accessibility:
            set_attribute(el, "internal_accessibility", accessibility)

        set_style(el, style_props)
        if el.yoga_node:
            apply_styles(el.yoga_node, style_props)

    # ── DOM Update (port of commitUpdate) ──

    def _update_dom_node(
        self, fiber: Fiber, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> None:
        """Mutate existing DOM node with changed props."""
        node = fiber.dom_node
        if not isinstance(node, DOMElement):
            return

        # In Ink, commitUpdate marks isStaticDirty on any static node update
        # (reconciler.ts line 303-305). However, Ink uses useLayoutEffect
        # which fires synchronously during commit, clearing static children
        # before the render. pyink uses use_effect (async), so we only mark
        # dirty when children actually change (detected by _sync_children_dom).
        # The _create_dom_node path already marks dirty on first mount.

        _skip = (
            "children", "key", "internal_transform",
            "internal_static", "internal_accessibility",
        )

        def _style_only(p: dict) -> dict:
            return {
                k: v for k, v in p.items()
                if k not in _skip and not k.startswith("aria_")
            }

        props_diff = _diff(old_props, new_props)
        style_diff = _diff(_style_only(old_props), _style_only(new_props))

        if not props_diff and not style_diff:
            return

        if props_diff:
            accessibility: dict[str, Any] = {}
            for key, value in props_diff.items():
                if key in ("children", "key"):
                    continue
                if key == "internal_transform":
                    node.internal_transform = value
                    continue
                if key == "internal_static":
                    node.internal_static = True
                    continue
                if key in ("aria_label", "aria_hidden", "aria_role", "aria_state"):
                    accessibility[key[5:]] = value
                    continue
            if accessibility:
                set_attribute(node, "internal_accessibility", accessibility)

        if style_diff:
            # Merge changed styles into existing style dict
            new_style = dict(node.style)
            for k, v in style_diff.items():
                if v is None:
                    new_style.pop(k, None)
                else:
                    new_style[k] = v
            set_style(node, new_style)
            if node.yoga_node:
                apply_styles(node.yoga_node, new_style)

    # ── DOM Child Sync ──

    def _sync_children_dom(self, parent_fiber: Fiber) -> None:
        """Sync DOM children to match fiber children order.

        Walks fiber children, collects their host DOM nodes (skipping
        component fibers), and ensures the parent DOM's children list
        matches in order.
        """
        parent_dom = self._find_host_dom(parent_fiber)
        if parent_dom is None or not isinstance(parent_dom, DOMElement):
            return

        # Collect target DOM children in fiber order
        target_children: list[DOMElement | TextNode] = []
        for child_fiber in parent_fiber.child_fibers:
            self._collect_host_nodes(child_fiber, target_children)

        # Fast path: if lists match exactly, nothing to do
        if len(parent_dom.children) == len(target_children):
            if all(
                parent_dom.children[i] is target_children[i]
                for i in range(len(target_children))
            ):
                return

        # If this is a static node and NEW children were added, mark dirty.
        # Don't mark dirty when children are removed (that's just cleanup).
        if parent_dom.internal_static and len(target_children) > len(parent_dom.children):
            self._root_node.is_static_dirty = True

        # Build set of target node ids
        target_ids = {id(n) for n in target_children}

        # Remove nodes no longer in target
        for old_child in list(parent_dom.children):
            if id(old_child) not in target_ids:
                remove_child(parent_dom, old_child)

        # Now append/reorder to match target order
        for i, child_node in enumerate(target_children):
            if child_node.parent is not parent_dom:
                # New child — append
                if i < len(parent_dom.children):
                    insert_before(parent_dom, child_node, parent_dom.children[i])
                else:
                    append_child(parent_dom, child_node)
            elif i < len(parent_dom.children) and parent_dom.children[i] is child_node:
                continue  # Already in correct position
            else:
                # Existing child in wrong position — move it
                remove_child(parent_dom, child_node)
                if i < len(parent_dom.children):
                    insert_before(parent_dom, child_node, parent_dom.children[i])
                else:
                    append_child(parent_dom, child_node)

    def _attach_new_children_dom(self, component_fiber: Fiber) -> None:
        """Attach newly created children's DOM nodes to the nearest ancestor.

        For component fibers only. Ensures that DOM nodes created during
        reconciliation are wired into the tree without disturbing siblings.
        Also marks is_static_dirty if the ancestor is a static node.
        """
        parent_dom = self._find_host_dom(component_fiber)
        if parent_dom is None or not isinstance(parent_dom, DOMElement):
            return

        added = False
        for child_fiber in component_fiber.child_fibers:
            nodes: list[DOMElement | TextNode] = []
            self._collect_host_nodes(child_fiber, nodes)
            for node in nodes:
                if node.parent is not parent_dom:
                    added = True
                    append_child(parent_dom, node)

        # Mark static dirty if we added children to a static node
        if added and parent_dom.internal_static:
            self._root_node.is_static_dirty = True

    def _find_host_dom(self, fiber: Fiber) -> DOMElement | TextNode | None:
        """Find the nearest host DOM node for a fiber.

        Component fibers don't have DOM nodes — walk UP the parent
        chain to find the nearest ancestor with a DOM node.
        """
        if fiber.dom_node is not None:
            return fiber.dom_node
        # Walk up parent chain to find nearest host ancestor
        parent = fiber.parent
        while parent is not None:
            if parent.dom_node is not None:
                return parent.dom_node
            parent = parent.parent
        return self._root_node

    def _collect_host_nodes(
        self, fiber: Fiber, out: list[DOMElement | TextNode]
    ) -> None:
        """Collect host DOM nodes from a fiber subtree.

        Component fibers are transparent — we collect their children's
        DOM nodes instead.
        """
        if fiber.dom_node is not None:
            out.append(fiber.dom_node)
            return
        # Component fiber — recurse into children
        for child in fiber.child_fibers:
            self._collect_host_nodes(child, out)

    # ── Context helpers ──

    def _is_fiber_inside_text(self, fiber: Fiber) -> bool:
        """Walk up fiber parents to determine isInsideText context."""
        parent = fiber.parent
        while parent:
            if parent.node_type in ("ink-text", "ink-virtual-text"):
                return True
            if parent.is_component:
                parent = parent.parent
                continue
            break
        return False

    # ── Fiber creation ──

    def _same_type(self, fiber: Fiber, vtype: str | Callable) -> bool:
        """Check if a fiber matches a VNode type (by identity for components, by name for hosts)."""
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

    # ── Destroy ──

    def _destroy_fiber(self, fiber: Fiber) -> None:
        """Cleanup effects and tear down subtree.

        DOM detachment is handled by ``_sync_children_dom`` (which
        removes nodes no longer in the target list). Here we only
        clean up effects and free yoga memory.
        """
        cleanup_effects(fiber)

        if fiber.dom_node is not None and isinstance(fiber.dom_node, DOMElement):
            if fiber.dom_node.internal_static:
                self._root_node.static_node = None

        for child in fiber.child_fibers:
            self._destroy_fiber(child)

    # ── Commit ──

    def _commit(self) -> None:
        """Port of resetAfterCommit + useLayoutEffect flush.

        Ink's sequence:
        1. resetAfterCommit → onImmediateRender (writes static)
        2. useLayoutEffect → setIndex(N) → synchronous re-render
        3. Re-render clears static children (internal, no output)
        4. useEffect fires after everything
        """
        if self.root_fiber:
            self.root_fiber.dom_node = self._root_node

        # Step 1: Notify App (renders frame with current DOM)
        self._on_commit()

        if self.root_fiber:
            # Step 2: Run layout effects (may call set_state)
            self._run_all_layout_effects(self.root_fiber)

            # Step 3: Flush layout-effect-triggered updates SILENTLY.
            # This is an internal synchronous re-render — do NOT notify
            # the App again. The DOM is updated but no frame is written.
            # This matches Ink where the layout effect re-render's
            # resetAfterCommit sees empty static → does nothing visible.
            self._flush_layout_updates()

            # Step 4: Run regular effects
            self._run_all_effects(self.root_fiber)

    def _flush_layout_updates(self) -> None:
        """Flush state updates triggered by layout effects.

        Re-renders dirty fibers synchronously WITHOUT notifying the App.
        Runs recursively until no more layout effects trigger updates.
        """
        if not self._dirty_fibers:
            return

        fibers = [self._dirty_fiber_map[fid] for fid in self._dirty_fibers]
        self._dirty_fibers.clear()
        self._dirty_fiber_map.clear()
        self._render_scheduled = False  # cancel pending async flush

        for fiber in fibers:
            self._render_fiber(
                fiber,
                is_inside_text=self._is_fiber_inside_text(fiber),
            )

        if self.root_fiber:
            self.root_fiber.dom_node = self._root_node

            # Recompute yoga layout after DOM changes from layout effects.
            # Without this, the yoga positions are stale (e.g. static node
            # still occupies space even after children are cleared).
            from pyink.layout.engine import build_yoga_tree

            build_yoga_tree(self._root_node)

        # Run layout effects on re-rendered fibers (may trigger more updates)
        if self.root_fiber:
            self._run_all_layout_effects(self.root_fiber)

        # Recurse if more updates were triggered
        if self._dirty_fibers:
            self._flush_layout_updates()

    def _run_all_layout_effects(self, fiber: Fiber) -> None:
        """Run layout effects synchronously during commit."""
        run_layout_effects(fiber)
        for child in fiber.child_fibers:
            self._run_all_layout_effects(child)

    def _run_all_effects(self, fiber: Fiber) -> None:
        run_effects(fiber)
        for child in fiber.child_fibers:
            self._run_all_effects(child)

    def unmount(self) -> None:
        if self.root_fiber:
            self._destroy_fiber(self.root_fiber)
            self.root_fiber = None
