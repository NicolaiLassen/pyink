from __future__ import annotations

from typing import Any, Callable

from pyink.fiber import EffectRecord
from pyink.hooks.context import get_current_fiber


def use_effect(
    setup: Callable[[], Callable | None], deps: tuple | None = None
) -> None:
    """React-like effect hook.

    setup() is called after render. If it returns a function, that function
    is called for cleanup before the next run or on unmount.
    deps=None means run every render. deps=() means run once on mount.
    """
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


def run_effects(fiber: Any) -> None:
    """Execute pending effects for a fiber. Called by reconciler after commit."""
    for record in fiber.effects:
        should_run = (
            record.prev_deps is None  # first run
            or record.deps is None  # no deps = run every time
            or record.deps != record.prev_deps
        )
        if should_run:
            if record.cleanup and callable(record.cleanup):
                record.cleanup()
            result = record.setup()
            record.cleanup = result if callable(result) else None


def cleanup_effects(fiber: Any) -> None:
    """Run all effect cleanups for a fiber (on unmount)."""
    for record in fiber.effects:
        if record.cleanup and callable(record.cleanup):
            record.cleanup()
            record.cleanup = None
