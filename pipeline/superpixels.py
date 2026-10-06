"""Superpixel generation, overlay rendering, and coral-pixel extraction."""

import numpy as np
from skimage.segmentation import slic, mark_boundaries
from skimage.measure import find_contours


def crop_fragment(img, bbox):
    """Crop the fragment region [x, y, w, h] from the full image."""
    x, y, w, h = bbox
    H, W = img.shape[:2]
    x0 = max(0, int(x)); y0 = max(0, int(y))
    x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
    return img[y0:y1, x0:x1, :]


def generate_superpixels(frag_rgb, n_segments):
    """Run SLIC on the fragment. Returns an int label map (same HxW)."""
    # slic wants float image in [0,1]; compactness tuned for photo regions.
    labels = slic(frag_rgb, n_segments=int(n_segments), compactness=10,
                  start_label=0, channel_axis=-1)
    return labels.astype(np.int32)


def superpixel_polygons(spl):
    """
    Return {superpixel_id: [(x, y), ...]} boundary polygon for each superpixel.
    Uses the largest contour per label.
    """
    polys = {}
    for spid in range(int(spl.max()) + 1):
        mask = (spl == spid)
        if not mask.any():
            continue
        contours = find_contours(mask.astype(float), 0.5)
        if not contours:
            continue
        # Largest contour (by point count) = outer boundary:
        c = max(contours, key=len)
        # find_contours returns (row, col) = (y, x); flip to (x, y):
        polys[spid] = [(pt[1], pt[0]) for pt in c]
    return polys


def extract_coral_pixels(frag_rgb, spl, coral_ids):
    """
    Return the R, G, B pixel arrays (uint8, sRGB) for all pixels belonging to
    coral-labeled superpixels in this fragment.
    """
    if not coral_ids:
        empty = np.array([], dtype=np.uint8)
        return empty, empty, empty
    mask = np.isin(spl, list(coral_ids))
    R = frag_rgb[:, :, 0][mask]
    G = frag_rgb[:, :, 1][mask]
    B = frag_rgb[:, :, 2][mask]
    return R, G, B