"""Demo classification: median cell color -> bleaching category."""

import numpy as np
from skimage.color import rgb2lab, lab2rgb

from card import geometry
from pipeline.alignment import PX_PER_MM
from pipeline import color_correction as cc

# Reference LAB for the four demo categories (in order):
CATEGORY_LABELS = ["Healthy", "Pale", "Partially Bleached", "Fully Bleached"]
CATEGORY_LAB = np.array([
    [36.0,  9.6, 13.4],   # Healthy
    [52.6, 31.2, 15.6],   # Pale
    [63.6,  6.4, 28.0],   # Partially Bleached
    [92.7, -0.8,  8.6],   # Fully Bleached
])


def category_badge_rgb():
    """Return the 4 category reference colors as 0-255 sRGB tuples (for badges)."""
    srgb = lab2rgb(CATEGORY_LAB.reshape(1, -1, 3)).reshape(-1, 3)
    srgb = np.clip(srgb, 0, 1)
    return [tuple(int(round(c * 255)) for c in row) for row in srgb]


def cell_median_lab(aligned_rgb, cell, inset=0.2):
    """
    Median LAB of a grid cell on the aligned (corrected) image.
    cell: (row, col, x, y, w, h) in mm. inset trims edges to avoid cell borders.
    Returns (L, a, b).
    """
    row, col, x, y, w, h = cell
    px = (x + inset * w) * PX_PER_MM
    py = (y + inset * h) * PX_PER_MM
    pw = w * (1 - 2 * inset) * PX_PER_MM
    ph = h * (1 - 2 * inset) * PX_PER_MM
    x0, y0 = int(round(px)), int(round(py))
    x1, y1 = int(round(px + pw)), int(round(py + ph))
    H, W = aligned_rgb.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    patch = aligned_rgb[y0:y1, x0:x1, :]
    if patch.size == 0:
        return None
    # aligned_rgb is uint8 sRGB (already color-corrected display image);
    # convert to LAB via sRGB assumption.
    srgb = patch.reshape(-1, 3).astype(np.float64) / 255.0
    lab = rgb2lab(srgb.reshape(1, -1, 3)).reshape(-1, 3)
    med = np.median(lab, axis=0)
    return tuple(med)


def classify_lab(lab):
    """Nearest-reference classification by LAB Euclidean (ΔE) distance.
    Returns (category_index, label, distance)."""
    lab = np.asarray(lab, dtype=np.float64)
    dists = np.linalg.norm(CATEGORY_LAB - lab, axis=1)
    idx = int(np.argmin(dists))
    return idx, CATEGORY_LABELS[idx], float(dists[idx])


def median_srgb_tuple(lab):
    """Convert a measured LAB to a 0-255 sRGB tuple (for showing the swatch)."""
    srgb = lab2rgb(np.asarray(lab, float).reshape(1, 1, 3)).reshape(3)
    srgb = np.clip(srgb, 0, 1)
    return tuple(int(round(c * 255)) for c in srgb)