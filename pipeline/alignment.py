"""
ArUco-based card alignment — replaces the MATLAB unwarpImageFun (Harris +
imregcorr phase correlation).

Plan (to implement once the new cards exist):
  1. Detect ArUco markers with cv2.aruco.
  2. Match detected marker corners (by ID) to known template coordinates.
  3. Compute a homography (cv2.findHomography) and warp
     (cv2.warpPerspective) to a canonical card geometry.
  4. Because geometry is now canonical, color-swatch locations become fixed
     known coordinates -> deterministic swatch sampling (may remove the
     manual 'ID Colors' step) and enables pixels-per-mm scale calibration.
"""

import numpy as np

# Placeholder for the chosen dictionary + ID->template-coordinate mapping.
# Fill in once card layout (dictionary, tag count/positions) is finalized.
ARUCO_DICT = None            # e.g. cv2.aruco.DICT_4X4_50
TEMPLATE_MARKER_COORDS = {}  # {marker_id: [(x,y) corners...]}


def align_to_card(img: np.ndarray) -> np.ndarray:
    """Return the perspective-corrected image. STUB: returns input unchanged."""
    # TODO: implement ArUco detection + homography.
    return img


def estimate_scale_mm_per_px(img: np.ndarray) -> float | None:
    """Optional: real-world scale from known tag size. STUB."""
    return None