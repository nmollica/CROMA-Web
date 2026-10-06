"""Manual segmentation stage callbacks."""

from dash import Input, Output, State, no_update, html
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState,
)

from ui import figures
from callbacks.shared import extract_last_rect


def register(app):

    @app.callback(
        Output("btn-start-labeling", "disabled"),
        Output("btn-start-labeling", "className"),
        Input("meta-site", "value"),
        Input("meta-date", "value"),
        Input("meta-timepoint", "value"),
        Input("meta-last-max-t", "value"),
        Input("meta-baseline-t", "value"),
        prevent_initial_call=False,
    )
    def toggle_start_labeling(site, date, timepoint, lastmax, baseline):
        vals = [site, date, timepoint, lastmax, baseline]
        ready = all(v and str(v).strip() for v in vals)
        if ready:
            return False, "w-100 btn btn-success"
        return True, "w-100 btn btn-secondary"

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("seg-phase", "data", allow_duplicate=True),
        Input("btn-start-labeling", "n_clicks"),
        EnrichState("state-store", "data"),
        State("meta-site", "value"),
        State("meta-date", "value"),
        State("meta-timepoint", "value"),
        State("meta-last-max-t", "value"),
        State("meta-baseline-t", "value"),
        prevent_initial_call=True,
    )
    def start_labeling(n, state, site, date, timepoint, lastmax, baseline):
        if not n:
            return no_update, no_update
        state.meta_site = site or ""
        state.meta_date = date or ""
        state.meta_timepoint = timepoint or ""
        state.meta_last_max_t = lastmax or ""
        state.meta_baseline_t = baseline or ""
        state.save_undo()
        return Serverside(state), "label"

    @app.callback(
        Output("seg-drawing", "data", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Input("btn-draw-sample", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def start_draw_sample(n, state):
        if not n:
            return no_update, no_update, no_update
        fig = figures.figure_from_segmentation(state, draw_enabled=True)
        return True, "Draw a rectangle around one coral fragment.", fig

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("seg-pending-rect", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("btn-confirm-sample", "n_clicks"),
        EnrichState("state-store", "data"),
        State("seg-pending-rect", "data"),
        State("samp-colony", "value"),
        State("samp-species", "value"),
        State("samp-tank", "value"),
        prevent_initial_call=True,
    )
    def confirm_sample(n, state, pending, colony, species, tank):
        if not n or pending is None:
            return no_update, no_update, no_update, no_update
        x, y, w, h = pending
        state.add_sample(x, y, w, h,
                         colony_id=colony or "", species=species or "",
                         tank=tank or "")
        state.save_undo()
        return (Serverside(state), None,
                figures.figure_from_segmentation(state),
                f"Sample #{state.n_samples()} saved.")

    @app.callback(
        Output("seg-pending-rect", "data", allow_duplicate=True),
        Output("seg-drawing", "data", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("btn-redraw-sample", "n_clicks"),
        prevent_initial_call=True,
    )
    def redraw_sample(n):
        if not n:
            return no_update, no_update, no_update
        return None, True, "Redraw the rectangle around the fragment."

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("btn-remove-sample", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def remove_sample(n, state):
        if not n:
            return no_update, no_update, no_update
        state.remove_last_sample()
        state.save_undo()
        return (Serverside(state), figures.figure_from_segmentation(state),
                f"{state.n_samples()} sample(s) remain.")

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("btn-finalize-segment", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def finalize_segment(n, state):
        if not n or state.n_samples() == 0:
            return no_update, no_update, no_update
        state.stage = "analyze"
        state.region_ids = list(range(len(state.subimg)))
        state.analyze_page = 0
        state.save_undo()
        # Show the first fragment (cropped) to start analysis:
        from pipeline import superpixels
        sub = state.current_subimg()
        frag = superpixels.crop_fragment(state.img, sub.bounding_box)
        fig = figures.figure_from_analysis(
            frag, title=sub.colony_id or "Fragment 1")
        return (Serverside(state), fig,
                f"Finalized {state.n_samples()} samples. Analyze each fragment.")