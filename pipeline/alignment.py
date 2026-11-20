"""ArUco-based card alignment: detect tags, compute homography, warp to template."""

import numpy as np
import cv2

from card import geometry
from card.template import ARUCO_DICT_NAME, CARD_W, CARD_H


# Pixels-per-mm for the warped (aligned) output. Higher = more resolution.
PX_PER_MM = 4.0
ALIGNED_W = int(round(CARD_W * PX_PER_MM))
ALIGNED_H = int(round(CARD_H * PX_PER_MM))


class AlignmentError(Exception):
    pass


def _aruco_detector():
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(getattr(aruco, ARUCO_DICT_NAME))
    params = aruco.DetectorParameters()
    return aruco.ArucoDetector(dictionary, params)


def detect_tags(img_rgb):
    """Detect ArUco tags. Returns {tag_id: 4x2 corner array (image px)}."""
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    detector = _aruco_detector()
    corners, ids, _ = detector.detectMarkers(gray)
    found = {}
    if ids is None:
        return found
    for c, i in zip(corners, ids.flatten()):
        found[int(i)] = c.reshape(4, 2)
    return found


def _template_tag_corners_mm():
    """{tag_id: 4x2 corner array in mm}, ordered TL,TR,BR,BL to match ArUco."""
    out = {}
    for tid, (x, y, size) in geometry.tag_positions().items():
        out[tid] = np.array([
            [x, y],                 # TL
            [x + size, y],          # TR
            [x + size, y + size],   # BR
            [x, y + size],          # BL
        ], dtype=np.float64)
    return out


def compute_homography(img_rgb, min_tags=4):
    """
    Match detected tags to template positions and compute the homography
    mapping image -> aligned template space (in pixels, PX_PER_MM scale).
    """
    detected = detect_tags(img_rgb)
    template = _template_tag_corners_mm()

    src, dst = [], []
    for tid, img_corners in detected.items():
        if tid not in template:
            continue
        tmpl_mm = template[tid]
        for (ix, iy), (mx, my) in zip(img_corners, tmpl_mm):
            src.append([ix, iy])
            dst.append([mx * PX_PER_MM, my * PX_PER_MM])  # mm -> aligned px

    n_tags = len(detected.keys() & template.keys())
    if n_tags < min_tags:
        raise AlignmentError(
            f"Only {n_tags} of the expected tags detected "
            f"(need at least {min_tags}). Check photo quality/lighting.")

    src = np.array(src, dtype=np.float64)
    dst = np.array(dst, dtype=np.float64)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        raise AlignmentError("Homography computation failed.")
    return H, n_tags


def align_image(img_rgb, min_tags=4):
    """
    Detect tags, compute homography, and warp the image to the canonical
    aligned template. Returns (aligned_rgb, n_tags_used).
    """
    H, n_tags = compute_homography(img_rgb, min_tags=min_tags)
    aligned = cv2.warpPerspective(img_rgb, H, (ALIGNED_W, ALIGNED_H))
    return aligned, n_tags


def swatch_rects_aligned(inset=0.2):
    """
    Return swatch rectangles in ALIGNED-image pixel coordinates.
    inset: fraction to shrink each swatch inward (per side) to avoid printed
           borders / edge bleed. 0.2 = sample the central 60% of each swatch.
    Returns list of (index, x, y, w, h) in aligned px.
    """
    from card import geometry
    rects = []
    for index, group, x, y, w, h in geometry.swatch_regions():
        # shrink toward center by `inset` fraction on each side:
        nx = x + inset * w
        ny = y + inset * h
        nw = w * (1 - 2 * inset)
        nh = h * (1 - 2 * inset)
        rects.append((
            index,
            nx * PX_PER_MM, ny * PX_PER_MM,
            nw * PX_PER_MM, nh * PX_PER_MM,
        ))
    return rects