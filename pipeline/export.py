"""Build the results table for export."""

import numpy as np
import pandas as pd
from skimage.color import rgb2lab

from pipeline.color_correction import _srgb_to_linear


def _median_linear_rgb(R, G, B):
    """R,G,B are uint8 sRGB arrays. Return median linear-RGB (0..1) per channel."""
    if R is None or len(R) == 0:
        return (np.nan, np.nan, np.nan)
    srgb = np.stack([R, G, B], axis=1).astype(np.float64) / 255.0
    lin = _srgb_to_linear(srgb)
    med = np.median(lin, axis=0)
    return tuple(med)


def _median_lab(R, G, B):
    """Median a* (and L*, b*) from the coral pixels, for the bleaching model."""
    if R is None or len(R) == 0:
        return (np.nan, np.nan, np.nan)
    srgb = np.stack([R, G, B], axis=1).astype(np.float64) / 255.0
    lab = rgb2lab(srgb.reshape(1, -1, 3)).reshape(-1, 3)
    med = np.median(lab, axis=0)
    return tuple(med)   # (L*, a*, b*)


def build_results_table(state):
    rows = []
    for idx in state.region_ids:
        sub = state.subimg[idx]
        rlin, glin, blin = _median_linear_rgb(sub.R, sub.G, sub.B)
        L, a, b = _median_lab(sub.R, sub.G, sub.B)
        n_pix = 0 if sub.R is None else int(len(sub.R))

        rows.append({
            "Image": state.filename or "",
            "Site": state.meta_site,
            "Date": state.meta_date,
            "Timepoint": state.meta_timepoint,
            "Last_Max_T": state.meta_last_max_t,
            "Baseline_T": state.meta_baseline_t,
            "Colony_ID": sub.colony_id,
            "Species": sub.species,
            "Tank": sub.tank,
            "Algorithm": getattr(state, "algo", ""),
            "N_coral_pixels": n_pix,
            "R_linear": rlin,
            "G_linear": glin,
            "B_linear": blin,
            "RplusG_linear": (rlin + glin) if not np.isnan(rlin) else np.nan,
            "Lstar": L,
            "astar": a,
            "bstar": b,
        })
    return pd.DataFrame(rows)