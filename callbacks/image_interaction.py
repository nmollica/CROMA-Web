"""Unified image-view interaction handler (relayout = rectangle drawing).

A SINGLE callback owns image-view.relayoutData so the swatch-capture (correct
stage) and sample-capture (segment stage) paths never conflict. It branches
on the current stage.
"""

from dash import Input, Output, State, no_update, html
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState, Input as EnrichInput
)

from ui import figures, controls
from callbacks.shared import extract_last_rect


def register(app):

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("controls-panel", "children", allow_duplicate=True),
        Output("swatch-status", "children", allow_duplicate=True),
        Output("armed-swatch", "data", allow_duplicate=True),
        Output("seg-pending-rect", "data", allow_duplicate=True),
        Output("seg-drawing", "data", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("image-view", "relayoutData"),
        EnrichState("state-store", "data"),
        State("armed-swatch", "data"),
        State("seg-drawing", "data"),
        prevent_initial_call=True,
    )
    def handle_draw(relayout, state, armed_idx, seg_drawing):
        NO = no_update
        none8 = (NO, NO, NO, NO, NO, NO, NO, NO)
        if state is None:
            return none8

        # --- Swatch capture (correction stage) ---
        if state.stage == "correct" and armed_idx is not None:
            shape = extract_last_rect(relayout)
            if shape is None:
                return none8
            x0, y0, x1, y1 = shape
            x, y = min(x0, x1), min(y0, y1)
            w, h = abs(x1 - x0), abs(y1 - y0)
            if w < 2 or h < 2:
                return none8
            state.set_swatch(armed_idx, x, y, w, h)
            state.save_undo()
            n_set = state.n_swatches_set()
            return (Serverside(state),
                    figures.figure_from_image(state.img, state, draw_enabled=False),
                    controls.correct_controls(state),
                    f"Swatch #{armed_idx + 1} set. ({n_set}/18 marked)",
                    None,              # disarm swatch
                    NO, NO, NO)        # segment outputs untouched

        # --- Sample capture (segment stage) ---
        if state.stage == "segment" and seg_drawing:
            shape = extract_last_rect(relayout)
            if shape is None:
                return none8
            x0, y0, x1, y1 = shape
            x, y = min(x0, x1), min(y0, y1)
            w, h = abs(x1 - x0), abs(y1 - y0)
            if w < 3 or h < 3:
                return none8
            H, W = state.img.shape[:2]
            if x <= 1 or y <= 1 or (x + w) >= (W - 1) or (y + h) >= (H - 1):
                return (NO,
                        figures.figure_from_segmentation(state, draw_enabled=False),
                        NO, NO, NO,
                        None, False,
                        html.Span("Rectangle touched the image edge — ignored.",
                                  className="text-warning"))
            pending = [x, y, w, h]
            return (NO,
                    figures.figure_from_segmentation(state, pending_rect=pending,
                                                     draw_enabled=False),
                    NO, NO, NO,
                    pending, False, "Enter sample details, then Confirm.")

        return none8

    @app.callback(
        Output("image-view", "className"),
        Input("armed-swatch", "data"),
        Input("seg-drawing", "data"),
        EnrichInput("state-store", "data"),
        prevent_initial_call=False,
    )
    def set_draw_cursor(armed_idx, seg_drawing, state):
        stage = getattr(state, "stage", None)
        if stage == "analyze":
            return "pick-mode"
        drawing = armed_idx is not None or bool(seg_drawing)
        return "" if drawing else "no-draw"