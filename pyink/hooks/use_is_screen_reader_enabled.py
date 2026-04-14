from __future__ import annotations

import os

from pyink.hooks.context import get_current_app


def use_is_screen_reader_enabled() -> bool:
    """Detect if a screen reader is enabled. Matches Ink's useIsScreenReaderEnabled hook.

    Checks INK_SCREEN_READER environment variable.

    Returns
    -------
    bool
        ``True`` if a screen reader is detected, ``False`` otherwise.
    """
    try:
        app = get_current_app()
        return getattr(app, "_is_screen_reader_enabled", False)
    except RuntimeError:
        return os.environ.get("INK_SCREEN_READER", "").lower() == "true"
