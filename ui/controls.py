"""Control-panel builders for each pipeline stage."""

from dash import dcc, html
import dash_bootstrap_components as dbc

from pipeline import color_correction


def upload_controls():
    return html.Div([
        html.H6("1. Load Image"),
        dcc.Upload(
            id="upload-image",
            children=html.Div([html.A("Upload a coral photo")," or drag & drop"]),
            style={"width": "100%", "height": "80px", "lineHeight": "80px",
                   "borderWidth": "1px", "borderStyle": "dashed",
                   "borderRadius": "6px", "textAlign": "center"},
            accept="image/*",
        ),
        html.Div(id="upload-status", className="mt-2 small text-muted"),
    ])


def correct_controls(state):
    swatch_rgbs = color_correction.reference_rgb_swatches()
    current_algo = getattr(state, "applied_algo", None) or "RBF Interpolation"

    swatch_buttons = []
    for i, rgb in enumerate(swatch_rgbs):
        is_set = any(getattr(r, "index", None) == i and r.is_set
                     for r in (state.rectangles if state else []))
        border = "3px solid #00ff00" if is_set else "1px solid #555"
        swatch_buttons.append(
            dbc.Button(
                "✓" if is_set else "",
                id={"type": "swatch-btn", "index": i},
                style={"backgroundColor": f"rgb{rgb}", "border": border,
                       "width": "100%", "height": "28px", "padding": "0",
                       "color": "#000", "fontWeight": "bold"},
                className="p-0",
            )
        )

    swatch_grid = html.Div(
        [dbc.Row([dbc.Col(swatch_buttons[r * 6 + c], width=2)
                  for c in range(6) if r * 6 + c < len(swatch_buttons)],
                 className="g-1 mb-1")
         for r in range((len(swatch_buttons) + 5) // 6)]
    )

    return html.Div([
        html.H6("2. Image Correction"),
        dbc.Button("Flatten (currently disabled)", id="btn-flatten", color="secondary",
                   size="sm", className="mb-2 w-100"),
        html.Hr(),
        html.Div("Click a color, then highlight it in the image:",
                 className="small text-muted mb-2"),
        swatch_grid,
        html.Hr(),
        dbc.Label("Color correction algorithm", className="small"),
        dbc.Select(id="dd-algo",
                   options=[
                       {"label": "None", "value": "None"},
                       {"label": "RBF Interpolation", "value": "RBF Interpolation"},
                       {"label": "Cross-Quadrat", "value": "Cross-Quadrat"},
                       {"label": "Cross-Linear", "value": "Cross-Linear"},
                   ],
                   value=current_algo, className="mb-2"),
        dbc.Button("Color Correct", id="btn-color", color="primary",
                   size="sm", className="mb-2 w-100"),
        dbc.Button("Finalize Corrections →", id="btn-finalize-correct",
                   color="secondary", size="sm", className="w-100",disabled=True),
    ])


def segment_controls(state, seg_phase, pending_rect):
    if seg_phase == "meta":
        return html.Div([
            html.H6("3. Label Image Info"),
            html.Div("Enter info shared by all fragments on this image:",
                     className="small text-muted mb-2"),
            dbc.Label("Site", className="small"),
            dbc.Input(id="meta-site", value=state.meta_site, size="sm",
                      className="mb-2"),
            dbc.Label("Date", className="small"),
            dbc.Input(id="meta-date", value=state.meta_date, size="sm",
                      className="mb-2"),
            dbc.Label("Timepoint", className="small"),
            dbc.Input(id="meta-timepoint", value=state.meta_timepoint, size="sm",
                      className="mb-2"),
            dbc.Label("Last Ramp Temperature", className="small"),
            dbc.Input(id="meta-last-max-t", value=state.meta_last_max_t,
                      size="sm", className="mb-2"),
            dbc.Label("Baseline Temperature", className="small"),
            dbc.Input(id="meta-baseline-t", value=state.meta_baseline_t,
                      size="sm", className="mb-3"),
            dbc.Button("Start Labeling Samples →", id="btn-start-labeling",
                       size="sm", className="w-100 btn btn-secondary", disabled=True),
        ])

    n = state.n_samples()

    if pending_rect is not None:
        d = state.next_sticky_defaults()
        return html.Div([
            html.H6("3. Label Sample"),
            dbc.Label("Colony / Fragment ID", className="small"),
            dbc.Input(id="samp-colony", value=d["colony_id"], size="sm",
                      className="mb-2"),
            dbc.Label("Species", className="small"),
            dbc.Input(id="samp-species", value=d["species"], size="sm",
                      className="mb-2"),
            dbc.Label("Tank", className="small"),
            dbc.Input(id="samp-tank", value=d["tank"], size="sm",
                      className="mb-3"),
            dbc.Button("Confirm Sample", id="btn-confirm-sample",
                       color="primary", size="sm", className="w-100 mb-2"),
            dbc.Button("Redraw", id="btn-redraw-sample",
                       color="secondary", size="sm", className="w-100"),
        ])

    return html.Div([
        html.H6("3. Draw Samples"),
        html.Div(f"{n} sample(s) labeled. Draw a box around a coral fragment.",
                 className="small text-muted mb-2"),
        dbc.Button("Draw Sample", id="btn-draw-sample", color="primary",
                   size="sm", className="w-100 mb-2"),
        dbc.Button("Remove Last Sample", id="btn-remove-sample",
                   color="secondary", size="sm", className="w-100 mb-2",
                   disabled=(n == 0)),
        html.Hr(),
        dbc.Button("Finalize Samples →", id="btn-finalize-segment",
                   size="sm", className=("w-100 btn btn-success" if n > 0 else "w-100 btn btn-secondary"),
                   disabled=(n == 0)),
    ])


def analyze_controls(state=None):
    if state is None or state.n_regions() == 0:
        return html.Div([
            html.H6("4. Analyze Samples"),
            html.Div("No samples to analyze.", className="small text-muted"),
        ])

    page = state.analyze_page
    n = state.n_regions()
    sub = state.current_subimg()
    has_spl = sub is not None and sub.spl is not None
    n_coral = len(sub.pixel_ids) if (sub and sub.pixel_ids) else 0
    is_last = (page == n - 1)

    return html.Div([
        html.H6("4. Analyze Samples"),
        html.Div(f"Fragment {page + 1} of {n}"
                 + (f" — {sub.colony_id}" if sub and sub.colony_id else ""),
                 className="small text-info mb-2"),

        dbc.Label("Superpixel detail", className="small"),
        dcc.Slider(id="sp-slider", min=50, max=300, step=10, value=sub.num_pix,
                   marks={50: "coarse", 300: "fine"},
                   tooltip={"placement": "bottom"}),
        dbc.Button("Generate Superpixels", id="btn-gen-sp", color="primary",
                   size="sm", className="w-100 mb-2 mt-2"),

        html.Div(id="sp-count",
                 children=(
                     (f"Click superpixels to mark coral (click again to unmark). "
                      f"{n_coral} marked.") if has_spl else
                     "Generate superpixels, then click to mark coral."),
                 className="small text-muted mb-2"),

        dbc.ButtonGroup([
            dbc.Button("← Prev", id="btn-prev-frag", color="secondary",
                       size="sm", disabled=(page == 0)),
            dbc.Button("Next →", id="btn-next-frag", color="secondary",
                       size="sm", disabled=(page >= n - 1)),
        ], className="w-100 mb-2"),

        html.Hr(),
        dbc.Button("Finalize Analysis →", id="btn-finalize-analyze",
                   size="sm",
                   className=("w-100 btn btn-success" if is_last
                              else "w-100 btn btn-secondary"),
                   disabled=(not is_last)),
    ])


def export_controls(state=None):
    return html.Div([
        html.H6("5. Export Results"),
        dbc.RadioItems(id="export-format",
                       options=[{"label": "Excel (.xlsx)", "value": "xlsx"},
                                {"label": "CSV (.csv)", "value": "csv"}],
                       value="xlsx", className="mb-2"),
        dbc.Button("Download Results", id="btn-export", color="success",
                   size="sm", className="w-100"),
        html.Div("Nothing is saved server-side.",
                 className="small text-muted mt-2"),
    ])