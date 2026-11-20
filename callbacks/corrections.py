"""Color-correction stage callbacks: swatch marking, overlay, correction."""

from dash import Input, Output, State, no_update, ALL, ctx, html
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState, Input as EnrichInput,
)

from pipeline import color_correction, alignment, lots
from ui import figures, layout as ui_layout
from callbacks.shared import extract_last_rect
from ui import controls

def register(app):

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("controls-panel", "children", allow_duplicate=True),
        Output("correct-status", "children", allow_duplicate=True),
        Input("btn-align", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def align_card(n, state):
        if not n:
            return no_update, no_update, no_update, no_update
        src = state.img_full if state.img_full is not None else state.img0
        try:
            aligned, n_tags = alignment.align_image(src)
            state.img = aligned
            state.img0 = aligned.copy()
            state.img_full = None
            state.aligned = True
            state.n_tags = n_tags
            state.rectangles = []
            state.autopopulate_swatches(alignment.swatch_rects_aligned())
            state.applied_algo = None

            # --- Read QR -> load lot reference (fallback to default if fails) ---
            lot_msg = ""
            try:
                lot_id = lots.read_qr(aligned)
                if lot_id:
                    state.lot_id = lot_id
                    state.lot_reference = lots.load_lot_reference(lot_id).tolist()
                    lot_msg = f" Lot '{lot_id}' reference loaded."
                else:
                    state.lot_reference = None
                    lot_msg = " QR not read — using default reference."
            except lots.LotError as e:
                state.lot_reference = None
                lot_msg = f" {e} Using default reference."

            state.save_undo()
            msg = html.Span(
                f"Aligned ({n_tags} tags). 18 swatches placed.{lot_msg}",
                className="text-success")
            return (Serverside(state),
                    figures.figure_from_image(state.img, state),
                    controls.correct_controls(state), msg)
        except alignment.AlignmentError as e:
            return (no_update, no_update, no_update,
                    html.Span(f"Alignment failed: {e}. Mark swatches manually.",
                              className="text-warning"))

    @app.callback(
        Output("armed-swatch", "data"),
        Output("swatch-status", "children", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Input({"type": "swatch-btn", "index": ALL}, "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def arm_swatch(clicks, state):
        if not ctx.triggered_id:
            return no_update, no_update, no_update
        if not any(clicks):
            return no_update, no_update, no_update
        idx = ctx.triggered_id["index"]
        n_set = state.n_swatches_set() if state else 0
        fig = figures.figure_from_image(state.img, state, draw_enabled=True)
        return (idx,
                f"Swatch #{idx + 1} armed — draw its rectangle. ({n_set}/18 marked)",
                fig)

    @app.callback(
        Output("panel-overlay", "style"),
        Input("armed-swatch", "data"),
        Input("seg-drawing", "data"),
        prevent_initial_call=False,
    )
    def toggle_overlay(armed_idx, seg_drawing):
        return ui_layout.overlay_style(
            armed_idx is not None or bool(seg_drawing))

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("correct-status", "children"),
        Input("btn-color", "n_clicks"),
        EnrichState("state-store", "data"),
        State("dd-algo", "value"),
        prevent_initial_call=True,
    )
    def do_color_correct(n, state, algorithm):
        if not n:
            return no_update, no_update, no_update
        if algorithm == "None":
            # Revert to the uncorrected original.
            state.img = state.img0.copy()
            state.applied_algo = "None"
            state.algo = "None"
            state.save_undo()
            return (Serverside(state),
                    figures.figure_from_image(state.img, state),
                    html.Span("Reverted to uncorrected image (None).",
                              className="text-muted"))
        try:
            corrected = color_correction.color_correct(
                state.img0, algorithm, state.rectangles,
                lot_reference=getattr(state, "lot_reference", None))
        except color_correction.CorrectionError as e:
            return no_update, no_update, html.Span(str(e),
                                                   className="text-warning")
        state.img = corrected
        state.algo = algorithm
        state.applied_algo = algorithm
        state.save_undo()
        fig = figures.figure_from_image(state.img, state)
        msg = html.Span(f"Applied: {algorithm}. Check that swatches blend in.",
                        className="text-success")
        return Serverside(state), fig, msg

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("seg-phase", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Input("btn-finalize-correct", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def finalize_corrections(n, state):
        if not n:
            return no_update, no_update, no_update
        state.stage = "segment"
        state.save_undo()
        fig = figures.figure_from_segmentation(state, draw_enabled=False)
        return Serverside(state), "meta", fig

    @app.callback(
        Output("btn-finalize-correct", "disabled"),
        Output("btn-finalize-correct", "color"),
        Input("dd-algo", "value"),
        EnrichInput("state-store", "data"),
        prevent_initial_call=False,
    )
    def toggle_finalize_correct(selected, state):
        applied = getattr(state, "applied_algo", None) if state else None
        enabled = (selected == "None" and applied in (None, "None")) or \
                  (selected == applied)
        if enabled:
            return False, "success"      # enabled: green
        return True, "secondary"         # disabled: grey