"""Lot reference loading: read the card QR, load per-lot measured swatch colors."""

import os
import csv
import numpy as np
import cv2

from card import geometry
from pipeline.alignment import PX_PER_MM

LOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "card", "lots")


class LotError(Exception):
    pass


def read_qr(aligned_rgb):
    qx, qy, qsize = geometry.qr_region()
    pad = qsize * 0.15
    x0 = int(max(0, (qx - pad) * PX_PER_MM))
    y0 = int(max(0, (qy - pad) * PX_PER_MM))
    x1 = int((qx + qsize + pad) * PX_PER_MM)
    y1 = int((qy + qsize + pad) * PX_PER_MM)
    crop = aligned_rgb[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    detector = cv2.QRCodeDetector()
    for k in range(4):
        rotated = np.rot90(gray, k)
        data, _, _ = detector.detectAndDecode(rotated)
        if data:
            return data
    return None

def load_lot_reference(lot_id):
    """
    Load the measured reference LAB for a lot id. Returns an (18,3) float array
    (L, a, b) indexed by swatch. Raises LotError if the file is missing/bad.
    """
    path = os.path.join(LOTS_DIR, f"{lot_id}.csv")
    if not os.path.exists(path):
        raise LotError(f"No reference file for lot '{lot_id}'.")
    ref = np.full((18, 3), np.nan)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            i = int(row["index"])
            if 0 <= i < 18:
                ref[i] = [float(row["L"]), float(row["a"]), float(row["b"])]
    if np.isnan(ref).any():
        raise LotError(f"Lot '{lot_id}' reference is incomplete.")
    return ref