"""Shared helpers used across callback modules."""


def extract_last_rect(relayout: dict):
    """Pull (x0, y0, x1, y1) of the most recently drawn rectangle from a
    Plotly relayoutData payload, or None if no complete rectangle is present."""
    if not relayout:
        return None
    if "shapes" in relayout and relayout["shapes"]:
        s = relayout["shapes"][-1]
        if s.get("type") == "rect":
            return s["x0"], s["y0"], s["x1"], s["y1"]
    coords = {}
    for k, v in relayout.items():
        for corner in ("x0", "y0", "x1", "y1"):
            if k.endswith("." + corner):
                coords[corner] = v
    if len(coords) == 4:
        return coords["x0"], coords["y0"], coords["x1"], coords["y1"]
    return None
