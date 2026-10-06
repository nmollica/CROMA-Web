"""Analysis stage callbacks: superpixels, click-to-label, navigation."""

from dash import Input, Output, State, no_update
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState,
)

from pipeline import superpixels
from ui import figures, controls


def _render_current(state):
    sub = state.current_subimg()
    frag = superpixels.crop_fragment(state.img, sub.bounding_box)
    title = sub.colony_id or f"Fragment {state.analyze_page + 1}"
    polys = None
    if sub.spl is not None:
        polys = superpixels.superpixel_polygons(sub.spl)
    return figures.figure_from_analysis(
        frag, polys=polys, coral_ids=set(sub.pixel_ids or []), title=title)


def register(app):

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("sp-count", "children", allow_duplicate=True),
        Input("btn-gen-sp", "n_clicks"),
        EnrichState("state-store", "data"),
        State("sp-slider", "value"),
        prevent_initial_call=True,
    )
    def generate_superpixels(n, state, n_seg):
        if not n:
            return no_update, no_update, no_update
        sub = state.current_subimg()
        if sub is None:
            return no_update, no_update, no_update
        frag = superpixels.crop_fragment(state.img, sub.bounding_box)
        sub.spl = superpixels.generate_superpixels(frag, n_seg)
        sub.num_pix = int(n_seg)
        sub.pixel_ids = []
        state.save_undo()
        return (Serverside(state), _render_current(state),
                "Click superpixels to mark coral (click again to unmark). 0 marked.")

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("sp-count", "children", allow_duplicate=True),
        Output("image-view", "clickData", allow_duplicate=True),
        Input("image-view", "clickData"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def click_superpixel(clickData, state):
        if not clickData or state is None or state.stage != "analyze":
            return no_update, no_update, no_update, no_update
        pt = clickData["points"][0]
        spid = pt.get("customdata")
        if spid is None:
            return no_update, no_update, no_update, no_update
        if isinstance(spid, list):
            spid = spid[0]
        state.toggle_coral_superpixel(int(spid))
        sub = state.current_subimg()
        n_coral = len(sub.pixel_ids) if sub else 0
        return (Serverside(state), _render_current(state),
                f"Click superpixels to mark coral (click again to unmark). "
                f"{n_coral} marked.",
                None)   # reset clickData so the same pixel can be re-clicked

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("controls-panel", "children", allow_duplicate=True),
        Input("btn-prev-frag", "n_clicks"),
        Input("btn-next-frag", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_fragment(prev_n, next_n, state):
        import dash
        ctx = dash.callback_context
        # Require a real triggering event from an actual button prop change:
        if not ctx.triggered or ctx.triggered[0]["value"] is None:
            return no_update, no_update, no_update
        trig = ctx.triggered_id
        if trig == "btn-prev-frag":
            state.analyze_page = max(0, state.analyze_page - 1)
        elif trig == "btn-next-frag":
            state.analyze_page = min(state.n_regions() - 1,
                                     state.analyze_page + 1)
        else:
            return no_update, no_update, no_update
        state.save_undo()
        return (Serverside(state), _render_current(state),
                controls.analyze_controls(state))

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Output("controls-panel", "children", allow_duplicate=True),
        Output("seg-status", "children", allow_duplicate=True),
        Input("btn-finalize-analyze", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def finalize_analysis(n, state):
        if not n:
            return no_update, no_update, no_update, no_update
        # Extract coral pixels for every fragment:
        for idx in state.region_ids:
            sub = state.subimg[idx]
            if sub.spl is None or not sub.pixel_ids:
                sub.R = sub.G = sub.B = None
                continue
            frag = superpixels.crop_fragment(state.img, sub.bounding_box)
            R, G, B = superpixels.extract_coral_pixels(
                frag, sub.spl, set(sub.pixel_ids))
            sub.R, sub.G, sub.B = R, G, B
        state.stage = "export"
        state.save_undo()
        from ui import figures as _f
        return (Serverside(state), _f.blank_figure(),
                controls.export_controls(state),
                "Analysis finalized. Ready to export.")