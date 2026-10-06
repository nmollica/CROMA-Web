"""App layout, stage indicator, and overlay-style helper."""

from dash import dcc, html
import dash_bootstrap_components as dbc

from ui import figures

STAGES = ["upload", "correct", "segment", "analyze", "export"]
STAGE_LABELS = {"upload": "Upload", "correct": "Correct",
                "segment": "Label", "analyze": "Analyze", "export": "Export"}

def overlay_style(visible: bool):
    return {
        "position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0,
        "backgroundColor": "rgba(20,20,20,0.6)", "zIndex": 1000,
        "cursor": "not-allowed", "borderRadius": "6px",
        "display": "block" if visible else "none",
    }


def stage_indicator(current_stage="upload"):
    order = STAGES
    cur_idx = order.index(current_stage) if current_stage in order else 0
    items = []
    for i, s in enumerate(order):
        label = STAGE_LABELS.get(s, s.capitalize())
        if i < cur_idx:
            link = dbc.NavLink(label, id=f"nav-{s}",
                               active=False, disabled=False,
                               className="text-success")
        elif i == cur_idx:
            link = dbc.NavLink(label, id=f"nav-{s}",
                               active=True, disabled=False)
        else:
            link = dbc.NavLink(label, id=f"nav-{s}",
                               active=False, disabled=True)
        items.append(dbc.NavItem(link))
    return dbc.Nav(items, pills=True, className="mb-3", id="stage-nav")


def build_layout():
    return dbc.Container(fluid=True, children=[
        dcc.Store(id="state-store", storage_type="session"),
        dcc.Store(id="session-id", storage_type="session"),
        dcc.Store(id="armed-swatch", storage_type="session", data=None),
        dcc.Store(id="seg-phase", storage_type="session", data="meta"),
        dcc.Store(id="seg-pending-rect", storage_type="session", data=None),
        dcc.Store(id="seg-drawing", storage_type="session", data=False),
        dcc.Store(id="last-stage", storage_type="session", data=None),
        dcc.Download(id="download-results"),

        html.H3("CoralRAMP Optical Measurement Analyzer", className="my-2"),
        html.Div(stage_indicator("upload"), id="stage-nav-wrap"),

        dbc.Row([
            dbc.Col(width=9, children=[
                dcc.Graph(id="image-view",
                    figure=figures.blank_figure(),
                    style={"height": "80vh"},
                    config={"scrollZoom": True}),
            ]),
            dbc.Col(width=3, children=[
                html.Div(
                    style={"position": "relative"},
                    children=[
                        html.Div(
                            id="panel-overlay",
                            style=overlay_style(False),
                            children=html.Div(
                                style={"padding": "12px"},
                                children=[
                                    html.Div("Drawing swatch — draw a rectangle "
                                             "on the image.",
                                             style={"color": "#fff",
                                                    "fontWeight": "bold",
                                                    "marginBottom": "8px"}),
                                    dbc.Button("Cancel", id="btn-cancel-swatch",
                                               color="warning", size="sm"),
                                ],
                            ),
                        ),
                        html.Div(id="controls-panel"),
                        html.Div(id="swatch-status",
                                 className="small mt-2 text-info"),
                        html.Div(id="correct-status", className="small mt-1"),
                        html.Div(id="seg-status",
                                 className="small mt-2 text-info"),
                        html.Hr(),
                        dbc.ButtonGroup([
                            dbc.Button("Undo", id="btn-undo",
                                       color="secondary", size="sm"),
                            dbc.Button("Redo", id="btn-redo",
                                       color="secondary", size="sm"),
                        ]),
                        html.Div(className="mt-2", children=[
                            dbc.Button("Start Over", id="btn-reset",
                                       color="danger", size="sm",
                                       className="me-2"),
                        ]),
                    ],
                ),
            ]),
        ]),
    ])