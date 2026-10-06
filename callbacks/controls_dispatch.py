"""Central controls-panel dispatcher."""

from dash import Input, Output, no_update
from dash_extensions.enrich import Input as EnrichInput, Output as EnrichOutput, State as EnrichState, Serverside

from ui import controls, layout, figures


def register(app):

    @app.callback(
        Output("controls-panel", "children"),
        EnrichInput("state-store", "data"),
        Input("seg-phase", "data"),
        Input("seg-pending-rect", "data"),
    )
    def render_controls(state, seg_phase, pending_rect):
        if state is None or getattr(state, "img", None) is None:
            return controls.upload_controls()
        if state.stage == "upload":
            return controls.upload_controls()
        if state.stage == "correct":
            return controls.correct_controls(state)
        if state.stage == "segment":
            return controls.segment_controls(state, seg_phase or "meta",
                                             pending_rect)
        if state.stage == "analyze":
            return controls.analyze_controls(state)
        if state.stage == "export":
            return controls.export_controls()
        return controls.upload_controls()


    @app.callback(
        Output("stage-nav-wrap", "children"),
        EnrichInput("state-store", "data"),
    )
    def update_stage_nav(state):
        stage = getattr(state, "stage", "upload") if state else "upload"
        return layout.stage_indicator(stage)

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Input("nav-upload", "n_clicks"),
        Input("nav-correct", "n_clicks"),
        Input("nav-segment", "n_clicks"),
        Input("nav-analyze", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def nav_back(u, c, s, a, state):
        import dash
        ctx = dash.callback_context
        if not ctx.triggered or ctx.triggered[0]["value"] is None:
            return no_update, no_update
        trig = ctx.triggered_id
        if not trig or state is None:
            return no_update, no_update
        target = trig.replace("nav-", "")
        order = ["upload", "correct", "segment", "analyze", "export"]
        if order.index(target) >= order.index(state.stage):
            return no_update, no_update
        state.stage = target
        state.save_undo()
        if target in ("upload", "correct"):
            fig = figures.figure_from_image(state.img, state)
        elif target == "segment":
            fig = figures.figure_from_segmentation(state)
        else:
            fig = figures.figure_from_image(state.img, state)
        return Serverside(state), fig