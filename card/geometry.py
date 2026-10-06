"""
App-facing accessors to the card geometry. Used later by ArUco alignment,
swatch auto-sampling, and grid-cell reading. Single source of truth = template.
"""

from .template import build_template


def tag_positions():
    """{tag_id: (x, y, size)} in mm (template coords)."""
    t = build_template()
    return {tag.tag_id: (tag.x, tag.y, tag.size) for tag in t.tags}


def swatch_regions():
    """List of (index, group, x, y, w, h) in mm."""
    t = build_template()
    return [(s.index, s.group, s.x, s.y, s.w, s.h) for s in t.swatches]


def grid_cells():
    """List of (row, col, x, y, w, h) in mm."""
    t = build_template()
    return [(c.row, c.col, c.x, c.y, c.w, c.h) for c in t.cells]