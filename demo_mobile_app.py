"""
CROMA Demo — mobile conference wizard.

Slimmed, phone-friendly linear flow reusing the CROMA pipeline:
  Capture -> Confirm Align -> Confirm Color -> Pick Cells -> Results

Run:  python demo_mobile_app.py   (port 8051)
"""

import base64
import uuid

import numpy as np
import plotly.graph_objects as go
from PIL import Image
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash_extensions.enrich import (
    DashProxy, ServersideOutputTransform, Serverside,
    Output as EnrichOutput, Input as EnrichInput, State as EnrichState,
)
from flask_caching import Cache

from pipeline import image_io, alignment, color_correction, lots
from pipeline import demo_classify as dc
from card import geometry


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = DashProxy(
    __name__,
    transforms=[ServersideOutputTransform()],
    external_stylesheets=[dbc.themes.DARKLY],
    title="CROMA Demo",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport",
                "content": "width=device-width, initial-scale=1, "
                           "maximum-scale=1, user-scalable=no"}],
)
server = app.server
cache = Cache(server, config={"CACHE_TYPE": "FileSystemCache",
                              "CACHE_DIR": "/tmp/croma_demo_cache",
                              "CACHE_DEFAULT_TIMEOUT": 60 * 30})

# Graph config: fully lock interactions so clicks are the ONLY gesture.
GRAPH_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showAxisDragHandles": False,
    "editable": False,
    "staticPlot": False,      # must stay False so clickData still fires
}


# ---------------------------------------------------------------------------
# Demo state
# ---------------------------------------------------------------------------
def new_demo_state():
    return {
        "step": "capture",
        "aligned": None,
        "corrected": None,
        "lot_reference": None,
        "selected_cells": [],
        "results": None,
    }


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------
def _blank_fig():
    fig = go.Figure()
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      paper_bgcolor="#222", plot_bgcolor="#222")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _img_fig(img_u8, overlay_cells=False, selected=None, classified=None,
             only_cells=None):
    """only_cells: if given, draw only these cell indices (for results view)."""
    h, w = img_u8.shape[:2]
    fig = go.Figure()
    fig.add_layout_image(dict(source=Image.fromarray(img_u8),
                              xref="x", yref="y", x=0, y=0,
                              sizex=w, sizey=h, sizing="stretch",
                              layer="below", xanchor="left", yanchor="top"))
    if overlay_cells:
        cells = geometry.grid_cells()
        badges = dc.category_badge_rgb()
        for i, (row, col, x, y, cw, ch) in enumerate(cells):
            if only_cells is not None and i not in only_cells:
                continue                      # skip non-analyzed cells
            px0 = x * alignment.PX_PER_MM
            py0 = y * alignment.PX_PER_MM
            pw = cw * alignment.PX_PER_MM
            ph = ch * alignment.PX_PER_MM
            xs = [px0, px0 + pw, px0 + pw, px0, px0]
            ys = [py0, py0, py0 + ph, py0 + ph, py0]
            is_sel = selected is not None and i in selected
            fill = "rgba(0,0,0,0.001)"
            line_color = "cyan"
            if classified is not None and i in classified:
                r, g, b = badges[classified[i]]
                fill = f"rgba({r},{g},{b},0.55)"
                line_color = "white"
            elif is_sel:
                fill = "rgba(30,110,255,0.45)"
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", line=dict(color=line_color, width=2),
                fill="toself", fillcolor=fill, hoveron="fills",
                hoverinfo="none", customdata=[i] * len(xs), showlegend=False))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode=False,
                      clickmode="event", paper_bgcolor="#222",
                      plot_bgcolor="#222", hovermode="closest",
                      showlegend=False)
    fig.update_xaxes(visible=False, range=[0, w])
    fig.update_yaxes(visible=False, range=[h, 0])
    return fig


# ---------------------------------------------------------------------------
# Layout — PERMANENT graph; router swaps only text (top) and buttons (bottom)
# ---------------------------------------------------------------------------
def _big_btn(label, bid, color="primary"):
    return dbc.Button(label, id=bid, color=color, size="lg",
                      className="w-100 my-2",
                      style={"padding": "16px", "fontSize": "1.2rem"})


app.layout = dbc.Container(fluid=True, className="px-2", children=[
    dcc.Store(id="demo-store", storage_type="memory"),
    dcc.Store(id="demo-session", storage_type="memory"),
    dcc.Store(id="selected-cells-client", storage_type="memory", data=[]),
    html.H4("CROMA Demo", className="text-center my-3"),

    dcc.Loading(
        id="scene-loading",
        type="circle",
        children=html.Div([
            html.Div(id="screen-top", className="text-center"),
            html.Div(id="view-wrap", children=[
                dcc.Graph(id="demo-view", figure=_blank_fig(),
                          config=GRAPH_CONFIG,
                          style={"width": "100%",
                                 "aspectRatio": f"{alignment.ALIGNED_W} / {alignment.ALIGNED_H}"}),
            ]),
            html.Div(id="upload-wrap", children=[
                dcc.Upload(
                    id="demo-upload",
                    children=_big_btn("📷 Take Photo", "demo-capture-btn", "primary"),
                    accept="image/*", multiple=False,
                ),
                html.Div(id="demo-status", className="text-center mt-2 small"),
            ]),
            html.Div(id="screen-bottom"),
            html.Div(id="loading-trigger", style={"display": "none"}),
        ]),
    ),

    html.Hr(),
    dbc.Button("🔄 Start Over", id="demo-global-restart", color="secondary",
               size="lg", className="w-100 my-2",
               style={"padding": "16px", "fontSize": "1.2rem",
                      "display": "none"}),
])


# ---------------------------------------------------------------------------
# Session bootstrap
# ---------------------------------------------------------------------------
@app.callback(
    EnrichOutput("demo-store", "data"),
    Output("demo-session", "data"),
    Input("demo-store", "data"),
    prevent_initial_call=False,
)
def init(existing):
    if existing is not None:
        return no_update, no_update
    return Serverside(new_demo_state()), str(uuid.uuid4())


@app.callback(
    EnrichOutput("demo-store", "data", allow_duplicate=True),
    Output("demo-upload", "contents"),
    Input("demo-global-restart", "n_clicks"),
    prevent_initial_call=True,
)
def global_restart(n):
    if not n:
        return no_update, no_update
    return Serverside(new_demo_state()), None


# ---------------------------------------------------------------------------
# Visibility: show/hide graph, upload, start-over by step
# ---------------------------------------------------------------------------
@app.callback(
    Output("view-wrap", "style"),
    Output("upload-wrap", "style"),
    Output("demo-global-restart", "style"),
    EnrichInput("demo-store", "data"),
)
def toggle_visibility(st):
    step = st.get("step", "capture") if st else "capture"
    show = {}
    hide = {"display": "none"}
    restart_style = {"padding": "16px", "fontSize": "1.2rem"}
    if step == "capture":
        restart_style["display"] = "none"
        return hide, show, restart_style          # graph hidden, upload shown
    return show, hide, restart_style              # graph shown, upload hidden


# ---------------------------------------------------------------------------
# Screen router: text (top) + buttons (bottom) only
# ---------------------------------------------------------------------------
@app.callback(
    Output("screen-top", "children"),
    Output("screen-bottom", "children"),
    EnrichInput("demo-store", "data"),
)
def render_screen(st):
    step = st.get("step", "capture") if st else "capture"
    if step == "capture":
        return (html.P("Take a photo of the coral card. "
                       "Fit the whole card in frame."), None)
    if step == "align":
        return (html.P("Does the card look flat and complete?"),
                _big_btn("✅ Alignment Looks Good", "demo-align-ok", "success"))
    if step == "color":
        return (html.P("Colors corrected. Do they look natural?"),
                _big_btn("✅ Colors Look Good", "demo-color-ok", "success"))
    if step == "cells":
        return (html.Div([
                    html.P("Tap each coral to analyze, then Analyze."),
                    html.Div(id="cell-count-text", children="0 selected",
                             className="fw-bold"),
                ]),
                _big_btn("🔬 Analyze Selected", "demo-cells-ok", "success"))
    if step == "results":
        return (html.Div([html.H5("Results", className="text-center"),
                          _results_cards(st)]),      # -> screen-top (above image)
                None)                                 # nothing below
    return (html.P("Take a photo of the coral card."), None)


def _results_cards(st):
    results = st.get("results") or []
    badges = dc.category_badge_rgb()
    cards = []
    for res in results:
        r, g, b = res["measured_rgb"]
        br, bg, bb = badges[res["cat_idx"]]
        cards.append(dbc.Card(className="mb-2", children=dbc.CardBody(
            html.Div(style={"display": "flex", "alignItems": "center"}, children=[
                html.Div(res["pos"], style={"fontWeight": "bold",
                                            "width": "60px"}),
                html.Div(style={"width": "48px", "height": "48px",
                                "backgroundColor": f"rgb({r},{g},{b})",
                                "borderRadius": "6px", "margin": "0 12px",
                                "border": "1px solid #555"}),
                dbc.Badge(res["label"],
                          style={"backgroundColor": f"rgb({br},{bg},{bb})",
                                 "color": "#000", "fontSize": "1rem"}),
            ]))))
    return html.Div(cards, className="mt-2")


# ---------------------------------------------------------------------------
# Figure setter: single callback owns demo-view.figure
# ---------------------------------------------------------------------------
@app.callback(
    Output("demo-view", "figure"),
    EnrichInput("demo-store", "data"),
)
def set_figure(st):
    if st is None:
        return _blank_fig()
    step = st["step"]
    if step == "align" and st["aligned"] is not None:
        return _img_fig(st["aligned"])
    if step == "color" and st["corrected"] is not None:
        return _img_fig(st["corrected"])
    if step == "cells" and st["corrected"] is not None:
        return _img_fig(st["corrected"], overlay_cells=True,
                        selected=st["selected_cells"])
    if step == "results" and st["corrected"] is not None:
        classified = {r["cell"]: r["cat_idx"] for r in (st["results"] or [])}
        return _img_fig(st["corrected"], overlay_cells=True,
                        classified=classified,
                        only_cells=set(classified.keys()))
    return _blank_fig()


# ---------------------------------------------------------------------------
# Capture -> align
# ---------------------------------------------------------------------------
@app.callback(
    EnrichOutput("demo-store", "data", allow_duplicate=True),
    Output("demo-status", "children"),
    Input("demo-upload", "contents"),
    EnrichState("demo-store", "data"),
    prevent_initial_call=True,
)
def on_capture(contents, st):
    if contents is None:
        return no_update, no_update
    _, b64 = contents.split(",", 1)
    full = image_io.decode_image(base64.b64decode(b64))
    try:
        aligned, n_tags = alignment.align_image(full)
    except alignment.AlignmentError as e:
        return no_update, f"Could not detect card ({e}). Try again."
    st = dict(st)
    st["aligned"] = aligned
    st["step"] = "align"
    return Serverside(st), ""


# ---------------------------------------------------------------------------
# Align confirm -> auto color correct
# ---------------------------------------------------------------------------
def _auto_swatch_rects():
    class _R:
        def __init__(self, index, x, y, w, h):
            self.index, self.x, self.y, self.w, self.h = index, x, y, w, h
            self.is_set = True
    return [_R(i, x, y, w, h)
            for (i, x, y, w, h) in alignment.swatch_rects_aligned()]


@app.callback(
    EnrichOutput("demo-store", "data", allow_duplicate=True),
    Input("demo-align-ok", "n_clicks"),
    Output("loading-trigger", "children", allow_duplicate=True),
    EnrichState("demo-store", "data"),
    prevent_initial_call=True,
)
def on_align_ok(n, st):
    if not n:
        return no_update
    st = dict(st)
    aligned = st["aligned"]
    try:
        lot_id = lots.read_qr(aligned)
        lot_ref = (lots.load_lot_reference(lot_id).tolist()
                   if lot_id else None)
    except Exception:
        lot_ref = None
    st["lot_reference"] = lot_ref
    rects = _auto_swatch_rects()
    st["corrected"] = color_correction.color_correct(
        aligned, "RBF Interpolation", rects, lot_reference=lot_ref)
    st["step"] = "color"
    return Serverside(st), ""


# ---------------------------------------------------------------------------
# Color confirm -> cells
# ---------------------------------------------------------------------------
@app.callback(
    EnrichOutput("demo-store", "data", allow_duplicate=True),
    Input("demo-color-ok", "n_clicks"),
    EnrichState("demo-store", "data"),
    prevent_initial_call=True,
)
def on_color_ok(n, st):
    if not n:
        return no_update
    st = dict(st)
    st["step"] = "cells"
    st["selected_cells"] = []
    return Serverside(st)


# ---------------------------------------------------------------------------
# Cell selection (tap to toggle) — only updates store; figure setter redraws
# ---------------------------------------------------------------------------
app.clientside_callback(
    """
    function(clickData, current) {
        if (!clickData) {
            return [window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update];
        }
        const pt = clickData.points[0];
        let cd = pt.customdata;
        if (Array.isArray(cd)) cd = cd[0];
        if (cd === undefined || cd === null) {
            return [window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update];
        }
        const cell = parseInt(cd);

        // curveNumber identifies which trace was clicked:
        const curve = pt.curveNumber;

        // Toggle selection set:
        let sel = current ? current.slice() : [];
        const pos = sel.indexOf(cell);
        let selected;
        if (pos === -1) { sel.push(cell); selected = true; }
        else { sel.splice(pos, 1); selected = false; }

        // Patch just the tapped trace's fillcolor:
        const patch = window.dash_clientside.no_update;
        const newFill = selected ? "rgba(30,110,255,0.45)"
                                 : "rgba(0,0,0,0.001)";
        // Use Plotly.restyle directly on the graph for instant update:
        const gd = document.querySelector("#demo-view .js-plotly-plot");
        if (gd) {
            Plotly.restyle(gd, {"fillcolor": newFill}, [curve]);
        }

        // Update count text + store; figure handled by restyle above.
        const countText = sel.length + " selected";
        return [sel, countText, null];
    }
    """,
    Output("selected-cells-client", "data"),
    Output("cell-count-text", "children"),
    Output("demo-view", "clickData"),
    Input("demo-view", "clickData"),
    State("selected-cells-client", "data"),
    prevent_initial_call=True,
)


app.clientside_callback(
    "function(n){ return []; }",
    Output("selected-cells-client", "data", allow_duplicate=True),
    Input("demo-global-restart", "n_clicks"),
    prevent_initial_call=True,
)


# ---------------------------------------------------------------------------
# Analyze -> results
# ---------------------------------------------------------------------------
@app.callback(
    EnrichOutput("demo-store", "data", allow_duplicate=True),
    Input("demo-cells-ok", "n_clicks"),
    State("selected-cells-client", "data"),
    EnrichState("demo-store", "data"),
    prevent_initial_call=True,
)
def on_analyze(n, selected_cells, st):
    if not n or not selected_cells:
        return no_update
    st = dict(st)
    cells = geometry.grid_cells()
    corrected = st["corrected"]
    results = []
    for i in sorted(selected_cells):
        row, col, x, y, cw, ch = cells[i]
        lab = dc.cell_median_lab(corrected, cells[i])
        if lab is None:
            continue
        idx, label, dist = dc.classify_lab(lab)
        results.append({"cell": i, "cat_idx": idx, "label": label,
                        "measured_rgb": dc.median_srgb_tuple(lab),
                        "pos": f"T{row+1}C{col+1}"})
    st["results"] = results
    st["step"] = "results"
    return Serverside(st)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8051, debug=True)