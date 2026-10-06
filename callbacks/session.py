"""Session bootstrap and undo/redo/reset callbacks."""

import uuid

import dash
from dash import Input, Output, no_update
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState,
)

from session_state import new_state
from ui import figures


def register(app):

    @app.callback(
        EnrichOutput("state-store", "data"),
        Output("session-id", "data"),
        Input("state-store", "data"),
        prevent_initial_call=False,
    )
    def init_session(existing):
        if existing is not None:
            return no_update, no_update
        return Serverside(new_state()), str(uuid.uuid4())

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure", allow_duplicate=True),
        Input("btn-undo", "n_clicks"),
        Input("btn-redo", "n_clicks"),
        Input("btn-reset", "n_clicks"),
        EnrichState("state-store", "data"),
        prevent_initial_call=True,
    )
    def undo_redo_reset(u, r, x, state):
        trig = dash.callback_context.triggered_id
        if trig == "btn-undo":
            state.undo()
        elif trig == "btn-redo":
            state.redo()
        elif trig == "btn-reset":
            state = new_state()
        fig = (figures.figure_from_image(state.img, state)
               if state.img is not None else figures.blank_figure())
        return Serverside(state), fig