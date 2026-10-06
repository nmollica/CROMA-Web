"""
CROMA card template — SINGLE SOURCE OF TRUTH for the physical card geometry.
(Units: millimeters, origin top-left, x->right, y->down.)
"""

from dataclasses import dataclass, field
import numpy as np

MM_PER_INCH = 25.4
CARD_W = 17 * MM_PER_INCH     # 431.8 mm
CARD_H = 11 * MM_PER_INCH     # 279.4 mm

DESIGN_VERSION = "v0.3"
BACKGROUND_RGB = (211, 211, 211)   # light neutral gray

ARUCO_DICT_NAME = "DICT_4X4_50"
ARUCO_TAG_MM = 22.0
ARUCO_EDGE_MARGIN = 5.0
SIDE_STRIP_W = 30.0

TOP_MARGIN = 6.0
BAND_GAP = 5.0

# Square swatches now:
SWATCH_SIZE = 20.0                # square: width == height
SWATCH_GAP = 4.0
SWATCH_LABEL_H = 0.0

# Metadata table (left side only, aligned with top swatch band):
METADATA_W_FRAC = 0.45           # fraction of content width used by metadata
METADATA_H = SWATCH_SIZE         # match swatch band height for alignment

CELL_H = 52
GRID_ROWS = 4
GRID_COLS = 6
CELL_GAP = 4.0
GRID_V_GAP = 3.0

CONTENT_X0 = SIDE_STRIP_W + 6.0
CONTENT_X1 = CARD_W - SIDE_STRIP_W - 6.0
CONTENT_W = CONTENT_X1 - CONTENT_X0


@dataclass
class Tag:
    tag_id: int
    x: float
    y: float
    size: float


@dataclass
class Swatch:
    index: int
    group: str
    x: float
    y: float
    w: float
    h: float
    nominal_rgb: tuple


@dataclass
class Cell:
    row: int
    col: int
    x: float
    y: float
    w: float
    h: float


@dataclass
class Template:
    card_w: float
    card_h: float
    tags: list = field(default_factory=list)
    swatches: list = field(default_factory=list)
    cells: list = field(default_factory=list)
    metadata_fields: list = field(default_factory=list)
    lot_text_pos: tuple = (0, 0)
    qr_pos: tuple = (0, 0)
    qr_size: float = 22.0


def _nominal_swatch_rgbs():
    from pipeline.color_correction import THEORETICAL_LAB
    from skimage.color import lab2rgb
    rgb = lab2rgb(THEORETICAL_LAB.reshape(1, -1, 3)).reshape(-1, 3)
    rgb = np.clip(rgb, 0, 1)
    return [tuple(int(round(c * 255)) for c in row) for row in rgb]


def build_template() -> Template:
    t = Template(card_w=CARD_W, card_h=CARD_H)
    nominal = _nominal_swatch_rgbs()

    # ---------------- ArUco tags ----------------
    s = ARUCO_TAG_MM
    m = ARUCO_EDGE_MARGIN

    # Width of a 6-square swatch group:
    group_w = 6 * SWATCH_SIZE + 5 * SWATCH_GAP

    # ----- TOP BAND: metadata (left) + grayscale swatches (right) -----
    # Swatch group label sits above the patches, so reserve label height.
    top_label_y = TOP_MARGIN
    top_band_y = TOP_MARGIN          # y of patches / metadata box

    # Top swatch group (grayscale, idx 0-5) on the RIGHT:
    gx = CONTENT_X1 - group_w
    for i in range(6):
        t.swatches.append(Swatch(
            index=i, group="grayscale",
            x=gx + i * (SWATCH_SIZE + SWATCH_GAP), y=top_band_y,
            w=SWATCH_SIZE, h=SWATCH_SIZE, nominal_rgb=nominal[i]))

    # Metadata table on the LEFT, aligned vertically with the swatch band:
    meta_w = CONTENT_W * METADATA_W_FRAC
    fields = [
        ("Site:",             1.3),
        ("Date:\nTimepoint:", 1.7),
        ("Species:",          1.4),
        ("Last Max T:",       1.0),
        ("Baseline T:",       1.0),
    ]
    total_weight = sum(w for _, w in fields)
    x = CONTENT_X0
    for lab, weight in fields:
        fw = meta_w * (weight / total_weight)
        t.metadata_fields.append(dict(
            label=lab, x=x, y=top_band_y, w=fw, h=METADATA_H))
        x += fw

    # Corner + top-mid tags vertically aligned with the top band.
    # Tag vertical center ~ center of the top band:
    band_cy = top_band_y + SWATCH_SIZE / 2.0
    tag_y_top = band_cy - s / 2.0

    # Corners (IDs 0-3 clockwise from TL). Top corners align to top band;
    # bottom corners sit near bottom edge.
    t.tags.append(Tag(0, m, tag_y_top, s))                           # TL
    t.tags.append(Tag(1, CARD_W - m - s, tag_y_top, s))              # TR
    t.tags.append(Tag(2, CARD_W - m - s, CARD_H - m - s, s))         # BR
    t.tags.append(Tag(3, m, CARD_H - m - s, s))                      # BL
    # Edge midpoints (IDs 4-7: top, right, bottom, left):
    # Top-mid tag between metadata (left) and swatch group (right):
    mid_gap_center = (CONTENT_X0 + meta_w + gx) / 2.0
    t.tags.append(Tag(4, CARD_W / 2 - s / 2, tag_y_top, s))    # top mid
    t.tags.append(Tag(5, CARD_W - m - s, CARD_H / 2 - s / 2, s))     # right mid
    t.tags.append(Tag(6, CARD_W / 2 - s / 2, CARD_H - m - s, s))     # bottom mid
    t.tags.append(Tag(7, m, CARD_H / 2 - s / 2, s))                  # left mid

    # ---------------- Sample grid ----------------
    grid_y0 = top_band_y + SWATCH_SIZE + BAND_GAP
    cell_w = (CONTENT_W - (GRID_COLS - 1) * CELL_GAP) / GRID_COLS
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cx = CONTENT_X0 + c * (cell_w + CELL_GAP)
            cy = grid_y0 + r * (CELL_H + GRID_V_GAP)
            t.cells.append(Cell(r, c, cx, cy, cell_w, CELL_H))
    grid_bottom = grid_y0 + GRID_ROWS * CELL_H + (GRID_ROWS - 1) * GRID_V_GAP

    # ---------------- Bottom swatch groups ----------------
    bot_band_y = grid_bottom + BAND_GAP
    # Left group = primary/secondary (idx 6-11):
    lx = CONTENT_X0
    for k, i in enumerate(range(6, 12)):
        t.swatches.append(Swatch(
            index=i, group="primary",
            x=lx + k * (SWATCH_SIZE + SWATCH_GAP), y=bot_band_y,
            w=SWATCH_SIZE, h=SWATCH_SIZE, nominal_rgb=nominal[i]))
    # Right group = coral-similar (idx 12-17):
    rx = CONTENT_X1 - group_w
    for k, i in enumerate(range(12, 18)):
        t.swatches.append(Swatch(
            index=i, group="coral",
            x=rx + k * (SWATCH_SIZE + SWATCH_GAP), y=bot_band_y,
            w=SWATCH_SIZE, h=SWATCH_SIZE, nominal_rgb=nominal[i]))

    # ---------------- Lot text + QR ----------------
    # Place in the open center-bottom between the two bottom swatch groups.
    center_x = (CONTENT_X0 + meta_w + rx) / 2.0
    t.qr_size = min(22.0, SWATCH_SIZE + 4)
    t.qr_pos = (m, grid_y0)
    t.lot_text_pos = (m + t.qr_size/2, grid_y0 + CELL_H + GRID_V_GAP)

    return t