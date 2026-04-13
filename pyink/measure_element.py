"""measureElement utility matching Ink's measure-element.ts.

Measures the dimensions of a DOMElement after layout has been computed.
"""
from __future__ import annotations

from pyink.dom import DOMElement


def measure_element(node: DOMElement) -> dict[str, int]:
    """Measure the dimensions of a Box element.

    Returns dict with 'width' and 'height' properties.
    Note: returns {width: 0, height: 0} before layout is computed.
    Call from use_effect or input handlers, not during render.

    Matches Ink's measureElement() function.
    """
    yn = node.yoga_node
    if yn is None:
        return {"width": 0, "height": 0}

    return {
        "width": int(yn.get_computed_width()),
        "height": int(yn.get_computed_height()),
    }
