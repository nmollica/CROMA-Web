"""
Croma-Web — Dash application entry point.

Multi-user architecture:
  * Each browser gets a `dcc.Store(storage_type="session")` holding a
    Serverside reference (a token) to that user's CromaState.
  * The actual CromaState (with numpy image arrays) lives in a server-side
    FileSystem cache, keyed by that token — never shared across users.
  * No cross-user globals. Safe for ~10 concurrent users.

For the trial: nothing is persisted beyond the session; the final step
produces an Excel/CSV the user downloads. Google-Drive saving comes later.
"""

import dash_bootstrap_components as dbc
from dash_extensions.enrich import DashProxy, ServersideOutputTransform

from flask_caching import Cache

from ui import layout as ui_layout

from callbacks import (
    session as cb_session, upload as cb_upload,
    image_interaction as cb_image_interaction,
    corrections as cb_correction,
    segmentation as cb_segmentation,
    analysis as cb_analysis,
    controls_dispatch as cb_controls_dispatch,
    export as cb_export
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = DashProxy(
    __name__,
    transforms=[ServersideOutputTransform()],
    external_stylesheets=[dbc.themes.DARKLY],
    title="Coral RAMP Optical Measurement Analyzer",
    suppress_callback_exceptions=True,
)
server = app.server

cache = Cache(server, config={
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DIR": "/tmp/croma_cache",
    "CACHE_DEFAULT_TIMEOUT": 60 * 60 * 4,
})

app.layout = ui_layout.build_layout()

cb_session.register(app)
cb_upload.register(app)
cb_correction.register(app)
cb_segmentation.register(app)
cb_analysis.register(app)
cb_controls_dispatch.register(app)
cb_export.register(app)
cb_image_interaction.register(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)