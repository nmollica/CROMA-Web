"""Image upload callback."""

import base64

from dash import Input, Output, State, no_update
from dash_extensions.enrich import (
    Serverside, Output as EnrichOutput, State as EnrichState,
)

from session_state import new_state
from pipeline import image_io
from ui import figures


def register(app):

    @app.callback(
        EnrichOutput("state-store", "data", allow_duplicate=True),
        Output("image-view", "figure"),
        Output("upload-status", "children"),
        Input("upload-image", "contents"),
        EnrichState("state-store", "data"),
        State("upload-image", "filename"),
        prevent_initial_call=True,
    )
    def handle_upload(contents, state, filename):
        if contents is None:
            return no_update, no_update, no_update
        _, b64 = contents.split(",", 1)
        img = image_io.decode_image(base64.b64decode(b64))
        img = image_io.resize_to_height(img, 1000)

        state = new_state()
        state.filename = filename
        state.img = img
        state.img0 = img.copy()
        state.crop_limits = [1, 1, img.shape[0], img.shape[1]]
        state.stage = "correct"
        state.save_undo()
        return (Serverside(state), figures.figure_from_image(img, state),
                f"Loaded: {filename}")