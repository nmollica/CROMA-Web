"""
Segmentation — port of splitImage/FinalizeLines (Hough line detection) and
the manual rectangle workflow. STUBS for now.
"""

import numpy as np


def detect_split_lines(img: np.ndarray, sensitivity: float) -> list:
    """Hough-based line detection. STUB: returns []."""
    # TODO: port calcLinesFun (cv2.HoughLinesP or skimage hough_line).
    return []


def label_regions_from_lines(img_shape, lines) -> np.ndarray:
    """Build labeled sub-regions from split lines. STUB."""
    return np.zeros(img_shape[:2], dtype=np.int32)