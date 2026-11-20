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
        full = image_io.decode_image(base64.b64decode(b64))   # full resolution

        state = new_state()
        state.filename = filename
        state.img_full = full                   # keep full-res for alignment
        # Display/working image: resized for the manual fallback path.
        disp = image_io.resize_to_height(full, 1000)
        state.img = disp
        state.img0 = disp.copy()
        state.crop_limits = [1, 1, disp.shape[0], disp.shape[1]]
        state.stage = "correct"
        state.save_undo()
        return (Serverside(state),
                figures.figure_from_image(state.img, state),
                f"Loaded: {filename}")