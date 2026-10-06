"""Image decode/resize utilities."""

import numpy as np
import cv2


def decode_image(raw: bytes) -> np.ndarray:
    """Decode raw image bytes to an RGB uint8 array."""
    arr = np.frombuffer(raw, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def resize_to_height(img: np.ndarray, height: int) -> np.ndarray:
    """Resize so the image is `height` px tall, preserving aspect ratio."""
    h, w = img.shape[:2]
    if h == height:
        return img
    new_w = int(round(w * height / h))
    return cv2.resize(img, (new_w, height), interpolation=cv2.INTER_AREA)