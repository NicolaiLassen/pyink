"""useEffect and useLayoutEffect hooks.

``use_layout_effect`` runs synchronously during commit (before render
output), matching React's ``useLayoutEffect``. ``use_effect`` runs after.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyink.fiber import EffectRecord
from pyink.hooks.context import get_current_fiber


def use_effect(
    setup: Callable[[], Callable | None], deps: tuple | None = None
) -> None:
    """Runs AFTER render output. Port of React's useEffect."""
    fiber = get_current_fiber()
    idx = fiber.effect_index
    fiber.effect_index += 1

    if idx >= len(fiber.effects):
        fiber.effects.append(
            EffectRecord(setup=setup, deps=deps, prev_deps=None)
        )
    else:
        record = fiber.effects[idx]
        record.setup = setup
        record.prev_deps = record.deps
        record.deps = deps


def use_layout_effect(
    setup: Callable[[], Callable | None], deps: tuple | None = None
) -> None:
    """Runs DURING commit, before render output.

    Port of React's useLayoutEffect. State updates triggered here
    cause a synchronous re-render before the frame is written.
    Used by Static to clear children before render.
    """
    fiber = get_current_fiber()
    idx = fiber.layout_effect_index
    fiber.layout_effect_index += 1

    if idx >= len(fiber.layout_effects):
        fiber.layout_effects.append(
            EffectRecord(setup=setup, deps=deps, prev_deps=None)
        )
    else:
        record = fiber.layout_effects[idx]
        record.setup = setup
        record.prev_deps = record.deps
        record.deps = deps


def _run_effect_list(records: list[EffectRecord]) -> None:
    """Run a list of effect records if their deps changed."""
    for record in records:
        should_run = (
            record.prev_deps is None
            or record.deps is None
            or record.deps != record.prev_deps
        )
        if should_run:
            if record.cleanup and callable(record.cleanup):
                record.cleanup()
            result = record.setup()
            record.cleanup = result if callable(result) else None


def run_effects(fiber: Any) -> None:
    """Execute pending useEffect records."""
    _run_effect_list(fiber.effects)


def run_layout_effects(fiber: Any) -> None:
    """Execute pending useLayoutEffect records."""
    _run_effect_list(fiber.layout_effects)


def cleanup_effects(fiber: Any) -> None:
    """Run all effect cleanups (on unmount)."""
    for record in fiber.effects:
        if record.cleanup and callable(record.cleanup):
            record.cleanup()
            record.cleanup = None
    for record in fiber.layout_effects:
        if record.cleanup and callable(record.cleanup):
            record.cleanup()
            record.cleanup = None
