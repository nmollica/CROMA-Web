"""Export stage callback."""

import re

from dash import Input, Output, State, no_update, dcc
from dash_extensions.enrich import State as EnrichState

from pipeline import export


def _safe_stem(filename):
    """Turn an image filename into a safe file stem (no extension, no bad chars)."""
    stem = (filename or "results").rsplit(".", 1)[0]
    stem = re.sub(r"[^A-Za-z0-9 _-]", "_", stem).strip()
    stem = re.sub(r"\s+", "_", stem)
    return stem or "results"


def register(app):

    @app.callback(
        Output("download-results", "data"),
        Input("btn-export", "n_clicks"),
        EnrichState("state-store", "data"),
        State("export-format", "value"),
        prevent_initial_call=True,
    )
    def do_export(n, state, fmt):
        if not n:
            return no_update
        df = export.build_results_table(state)
        stem = _safe_stem(getattr(state, "filename", None))
        if fmt == "csv":
            return dcc.send_data_frame(df.to_csv, f"{stem}_results.csv",
                                       index=False)
        return dcc.send_data_frame(df.to_excel, f"{stem}_results.xlsx",
                                   index=False)