"""
Per-session state model for CROMA-Web.

This replaces the MATLAB nested-function shared variables (state, UndoStack,
colorRoi, etc.). Each browser session gets its own CromaState instance, so
concurrent users never see each other's data.

The state is kept deliberately serializable (numpy arrays + plain dicts/lists)
so that later we can (a) push it to a user's Google Drive, and (b) migrate to
a scale-to-zero platform like Cloud Run without re-architecting.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import numpy as np
import copy

@dataclass
class SwatchRect:
    """One color-card swatch rectangle, tied to a reference color index."""
    index: int                    # 0..17, maps to REFERENCE_LAB row
    x: float = 0.0                # top-left (image pixel coords)
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @property
    def is_set(self) -> bool:
        return self.w > 0 and self.h > 0

@dataclass
class SubImage:
    """One coral fragment sub-region."""
    bounding_box: list = field(default_factory=list)   # [x, y, w, h]
    selected: bool = True
    # --- per-sample metadata ---
    colony_id: str = ""
    species: str = ""
    tank: str = ""
    # --- analysis results (filled later) ---
    spl: np.ndarray | None = None
    pixel_ids: list = field(default_factory=list)
    pixel_no_ids: list = field(default_factory=list)
    num_pix: int = 100
    R: np.ndarray | None = None
    G: np.ndarray | None = None
    B: np.ndarray | None = None


@dataclass
class CromaState:
    """
    Full analysis state for a single user session.
    Mirrors the MATLAB `state` struct, reorganized for a web workflow.
    """
    # --- image data ---
    filename: str | None = None
    img: np.ndarray | None = None          # current working image (RGB uint8)
    img0: np.ndarray | None = None         # snapshot before color correction
    crop_limits: list = field(default_factory=list)

    # --- correction stage ---
    unwarp_flag: bool = False
    bg_correction_flag: bool = False
    algo: str = "None"
    applied_algo: str | None = None
    rectangles: list = field(default_factory=list)   # color-card swatch ROIs

    # --- helper functions ---
    def set_swatch(self, index: int, x, y, w, h):
        """Insert or replace the rectangle for a given swatch index."""
        # remove any existing rect for this index
        self.rectangles = [r for r in self.rectangles
                           if getattr(r, "index", None) != index]
        from session_state import SwatchRect  # local import avoids circularity
        self.rectangles.append(SwatchRect(index=index, x=x, y=y, w=w, h=h))

    def n_swatches_set(self) -> int:
        return sum(1 for r in self.rectangles if getattr(r, "is_set", False))

    # --- segmentation stage ---
    lines: list = field(default_factory=list)
    bwl: np.ndarray | None = None          # labeled split regions
    subimg: list[SubImage] = field(default_factory=list)
    region_ids: list = field(default_factory=list)
    # per-image metadata
    meta_site: str = ""
    meta_date: str = ""
    meta_timepoint: str = ""
    meta_last_max_t: str = ""
    meta_baseline_t: str = ""
    # sticky defaults for per-sample entry
    sticky_species: str = ""
    sticky_tank: str = ""
    sticky_colony_id: str = ""
    

    def add_sample(self, x, y, w, h, colony_id, species, tank):
        """Add a confirmed coral-fragment sample and update sticky defaults."""
        sub = SubImage(
            bounding_box=[int(round(x)), int(round(y)),
                          int(round(w)), int(round(h))],
            selected=True,
            colony_id=colony_id, species=species, tank=tank,
        )
        self.subimg.append(sub)
        self.region_ids = list(range(len(self.subimg)))
        # Update sticky memory for the next fragment:
        self.sticky_species = species
        self.sticky_tank = tank
        self.sticky_colony_id = colony_id

    def next_sticky_defaults(self):
        """Values to pre-fill the next sample form.
        Species & tank carry over; colony id auto-increments if numeric."""
        next_id = _increment_id(self.sticky_colony_id)
        return dict(colony_id=next_id,
                    species=self.sticky_species,
                    tank=self.sticky_tank)

    def remove_last_sample(self):
        if self.subimg:
            self.subimg.pop()
            self.region_ids = list(range(len(self.subimg)))
            if self.subimg:
                last = self.subimg[-1]
                self.sticky_colony_id = last.colony_id
                self.sticky_species = last.species
                self.sticky_tank = last.tank
            else:
                self.sticky_colony_id = ""
                self.sticky_species = ""
                self.sticky_tank = ""

    def n_samples(self) -> int:
        return len(self.subimg)

    def sample_id_code(self, sub: "SubImage") -> str:
        """Derive an export IDCode from structured fields (name not stored)."""
        image_stem = (self.filename or "image").rsplit(".", 1)[0]
        parts = [image_stem, self.meta_site, self.meta_date,
                 sub.species, sub.tank, sub.colony_id]
        return "-".join(p if p else "NA" for p in parts)

    # --- analysis stage ---
    analyze_page: int = 0     # which fragment (index into region_ids) is shown

    def current_region_index(self):
        """Index into self.subimg for the fragment currently being analyzed."""
        if not self.region_ids:
            return None
        self.analyze_page = max(0, min(self.analyze_page, len(self.region_ids) - 1))
        return self.region_ids[self.analyze_page]

    def current_subimg(self):
        idx = self.current_region_index()
        return self.subimg[idx] if idx is not None else None

    def n_regions(self):
        return len(self.region_ids)

    def toggle_coral_superpixel(self, spid: int):
        """Toggle a superpixel id in the current fragment's coral set."""
        sub = self.current_subimg()
        if sub is None or sub.spl is None:
            return
        ids = set(sub.pixel_ids or [])
        if spid in ids:
            ids.discard(spid)
        else:
            ids.add(spid)
        sub.pixel_ids = sorted(ids)

    # --- workflow tracking ---
    stage: str = "upload"   # upload -> correct -> segment -> analyze -> export

    # --- undo/redo ---
    # Kept simple for the trial: a bounded list of deep-copied snapshots.
    # (Your MATLAB diff-based stack is more memory-efficient; we can port that
    #  later if memory becomes a concern with ~10 concurrent users.)
    _undo_stack: list = field(default_factory=list, repr=False)
    _undo_index: int = -1

    # ---------------- undo / redo ----------------
    def save_undo(self, max_depth: int = 10):
        """Snapshot current state (excluding the stacks themselves)."""
        snap = self._snapshot()
        # Drop any redo history past the current point:
        self._undo_stack = self._undo_stack[: self._undo_index + 1]
        self._undo_stack.append(snap)
        if len(self._undo_stack) > max_depth:
            self._undo_stack.pop(0)
        self._undo_index = len(self._undo_stack) - 1

    def undo(self):
        if self._undo_index > 0:
            self._undo_index -= 1
            self._restore(self._undo_stack[self._undo_index])

    def redo(self):
        if self._undo_index < len(self._undo_stack) - 1:
            self._undo_index += 1
            self._restore(self._undo_stack[self._undo_index])

    def _snapshot(self) -> dict:
        d = {k: copy.deepcopy(v) for k, v in self.__dict__.items()
             if not k.startswith("_undo")}
        return d

    def _restore(self, snap: dict):
        for k, v in snap.items():
            setattr(self, k, copy.deepcopy(v))

def _increment_id(val: str) -> str:
    """If val ends in a number, increment it (e.g. 'C5'->'C6', '5'->'6').
    Otherwise return val unchanged (sticky)."""
    if not val:
        return ""
    import re
    m = re.search(r"(\d+)$", val)
    if not m:
        return val            # non-numeric: just keep it sticky
    num = m.group(1)
    prefix = val[:m.start()]
    return f"{prefix}{int(num) + 1}"

def new_state() -> CromaState:
    return CromaState()