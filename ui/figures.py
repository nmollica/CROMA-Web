"""Figure builders for the image view."""

import plotly.express as px
import plotly.graph_objects as go

from pipeline import color_correction


def blank_figure():
    fig = go.Figure()
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      paper_bgcolor="#222", plot_bgcolor="#222")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _base_image_fig(img, newshape_color="cyan"):
    fig = px.imshow(img)
    fig.update_traces(hovertemplate=None, hoverinfo="skip")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode="drawrect",
                      paper_bgcolor="#222", plot_bgcolor="#222",
                      hovermode=False,
                      newshape=dict(line=dict(color=newshape_color, width=2)))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def figure_from_image(img, state=None, draw_enabled=False):
    dragmode = "drawrect" if draw_enabled else False
    fig = px.imshow(img)
    fig.update_traces(hovertemplate=None, hoverinfo="skip")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode=dragmode,
                      paper_bgcolor="#222", plot_bgcolor="#222",
                      hovermode=False,
                      newshape=dict(line=dict(color="cyan", width=2)))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    if state is not None and state.rectangles:
        swatch_rgbs = color_correction.reference_rgb_swatches()
        shapes = []
        for r in state.rectangles:
            if not getattr(r, "is_set", False):
                continue
            rgb = swatch_rgbs[r.index]
            shapes.append(dict(type="rect", x0=r.x, y0=r.y,
                               x1=r.x + r.w, y1=r.y + r.h,
                               line=dict(color=f"rgb{rgb}", width=2),
                               editable=False))
        if shapes:
            fig.update_layout(shapes=shapes)
    return fig


def figure_from_segmentation(state, pending_rect=None, draw_enabled=False):
    dragmode = "drawrect" if draw_enabled else False
    fig = px.imshow(state.img)
    fig.update_traces(hovertemplate=None, hoverinfo="skip")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode=dragmode,
                      paper_bgcolor="#222", plot_bgcolor="#222",
                      hovermode=False,
                      newshape=dict(line=dict(color="yellow", width=2)))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    shapes = []
    for sub in state.subimg:
        if not sub.bounding_box:
            continue
        bx, by, bw, bh = sub.bounding_box
        shapes.append(dict(type="rect", x0=bx, y0=by, x1=bx + bw, y1=by + bh,
                           line=dict(color="cyan", width=2), editable=False))
    if pending_rect is not None:
        px_, py_, pw_, ph_ = pending_rect
        shapes.append(dict(type="rect", x0=px_, y0=py_,
                           x1=px_ + pw_, y1=py_ + ph_,
                           line=dict(color="yellow", width=2, dash="dash"),
                           editable=False))
    if shapes:
        fig.update_layout(shapes=shapes)
    for i, sub in enumerate(state.subimg):
        if not sub.bounding_box:
            continue
        bx, by, bw, bh = sub.bounding_box
        label = sub.colony_id or f"#{i+1}"
        fig.add_annotation(x=bx + 2, y=by + 2, text=label, showarrow=False,
                           font=dict(color="cyan", size=12),
                           xanchor="left", yanchor="top")
    return fig


def figure_from_analysis(display_img, polys=None, coral_ids=None, title=None):
    import plotly.graph_objects as go
    from PIL import Image
    coral_ids = set(coral_ids or [])
    h, w = display_img.shape[:2]

    fig = go.Figure()

    # Image as a non-interactive background layout image (not a trace):
    fig.add_layout_image(dict(
        source=Image.fromarray(display_img),
        xref="x", yref="y", x=0, y=0,
        sizex=w, sizey=h, sizing="stretch",
        layer="below", xanchor="left", yanchor="top",
    ))

    if polys:
        for spid, pts in polys.items():
            xs = [p[0] for p in pts] + [pts[0][0]]
            ys = [p[1] for p in pts] + [pts[0][1]]
            selected = spid in coral_ids
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color="cyan", width=1),
                fill="toself",
                fillcolor=("rgba(30,110,255,0.45)" if selected
                           else "rgba(0,0,0,0.001)"),
                hoveron="fills", hoverinfo="none",
                customdata=[spid] * len(xs), showlegend=False,
            ))

    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      dragmode=False, clickmode="event",
                      paper_bgcolor="#222", plot_bgcolor="#222",
                      hovermode="closest", showlegend=False)
    # y axis must be reversed so image isn't upside down, and ranges locked:
    fig.update_xaxes(visible=False, range=[0, w], constrain="domain")
    fig.update_yaxes(visible=False, range=[h, 0], scaleanchor="x")

    if title:
        fig.add_annotation(x=5, y=5, text=title, showarrow=False,
                           font=dict(color="red", size=16),
                           xanchor="left", yanchor="top")
    return fig