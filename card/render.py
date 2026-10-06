"""
Render the CROMA card template to a printable SVG (and optionally PDF).

Usage:
    python -m card.render --lot LOT-2026A --out card_draft

Produces card_draft.svg (always) and card_draft.pdf (if cairosvg available).
"""

import argparse
import base64
import io

import cv2
import numpy as np
import qrcode

from .template import (build_template, BACKGROUND_RGB, DESIGN_VERSION,
                       ARUCO_DICT_NAME)

MM = 1.0  # we author the SVG directly in mm units


def _rgb_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _aruco_svg_group(tag, dict_name):
    """Return an SVG <g> drawing the ArUco marker as exact black/white cells."""
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(getattr(aruco, dict_name))
    # Generate at the marker's native bit resolution (with border):
    # DICT_4X4_50 -> 4x4 data + 1-cell black border = 6x6 cells.
    bits = 6
    img = aruco.generateImageMarker(dictionary, tag.tag_id, bits)  # 6x6, 0/255
    cell = tag.size / bits
    rects = []
    for yy in range(bits):
        for xx in range(bits):
            if img[yy, xx] == 0:  # black cell
                rx = tag.x + xx * cell
                ry = tag.y + yy * cell
                rects.append(
                    f'<rect x="{rx:.3f}" y="{ry:.3f}" '
                    f'width="{cell:.3f}" height="{cell:.3f}" fill="#000000"/>')
    # White backing behind the tag so it reads cleanly on gray background:
    backing = (f'<rect x="{tag.x:.3f}" y="{tag.y:.3f}" '
               f'width="{tag.size:.3f}" height="{tag.size:.3f}" fill="#ffffff"/>')
    return f'<g>{backing}{"".join(rects)}</g>'


def _qr_svg_image(data, x, y, size):
    """Embed a QR code as a PNG data-URI <image> at (x,y) size mm."""
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f'<image x="{x:.3f}" y="{y:.3f}" width="{size:.3f}" '
            f'height="{size:.3f}" href="data:image/png;base64,{b64}"/>')


def render_svg(lot_id: str) -> str:
    t = build_template()
    W, H = t.card_w, t.card_h
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" '
        f'font-family="Arial, Helvetica, sans-serif">')

    # Background (light gray):
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" '
                 f'fill="{_rgb_hex(BACKGROUND_RGB)}"/>')

    # Metadata row:
    for f in t.metadata_fields:
        parts.append(
            f'<rect x="{f["x"]:.2f}" y="{f["y"]:.2f}" width="{f["w"]:.2f}" '
            f'height="{f["h"]:.2f}" fill="none" stroke="#333" stroke-width="0.4"/>')

        lines = f["label"].split("\n")
        tx = f["x"] + 1.5
        ty = f["y"] + 5          # baseline of first line
        line_h = 12             # line spacing (mm); tune to taste
        tspans = "".join(
            f'<tspan x="{tx:.2f}" y="{ty + i*line_h:.2f}">{ln}</tspan>'
            for i, ln in enumerate(lines)
        )
        parts.append(
            f'<text font-size="4" fill="#333">{tspans}</text>')

    # Sample grid cells (visibly outlined):
    for c in t.cells:
        parts.append(
            f'<rect x="{c.x:.2f}" y="{c.y:.2f}" width="{c.w:.2f}" '
            f'height="{c.h:.2f}" fill="none" stroke="#333" stroke-width="0.5"/>')
        label = f"T{c.row + 1}C{c.col + 1}"
        parts.append(
            f'<text x="{c.x + 1.8:.2f}" y="{c.y + 5:.2f}" font-size="4" '
            f'fill="#0047d6">{label}</text>')

    for sw in t.swatches:
        parts.append(
            f'<rect x="{sw.x:.2f}" y="{sw.y:.2f}" width="{sw.w:.2f}" '
            f'height="{sw.h:.2f}" fill="{_rgb_hex(sw.nominal_rgb)}" '
            f'stroke="#333" stroke-width="0.3"/>')

    # ArUco tags:
    for tag in t.tags:
        parts.append(_aruco_svg_group(tag, ARUCO_DICT_NAME))

    # Lot text (human-readable) + QR:
    lx, ly = t.lot_text_pos
    line1 = "Designed for use with"
    line2 = f"CROMA {DESIGN_VERSION} | {lot_id}"
    line_sep = 5.0   # perpendicular spacing between the two stacked lines (mm)
    tspans = (
        f'<tspan x="{lx:.2f}" y="{ly:.2f}" font-size="4" '
        f'font-weight="bold">{line1}</tspan>'
        f'<tspan x="{lx:.2f}" y="{ly + line_sep:.2f}" font-size="4" '
        f'font-weight="bold">{line2}</tspan>'
    )
    parts.append(
        f'<text text-anchor="middle" fill="#000" '
        f'transform="rotate(-90, {lx:.2f}, {ly:.2f})">{tspans}</text>')
    qx, qy = t.qr_pos
    parts.append(_qr_svg_image(lot_id, qx, qy, t.qr_size))

    parts.append('</svg>')
    return "\n".join(parts)

def _rgb_to_cmyk(rgb):
    """
    Standard (naive) sRGB 0-255 -> CMYK conversion, values as percentages 0-100.

    NOTE: This is a device-independent approximation, NOT matched to any
    specific printer/paper/profile. Treat these as TARGET values to give the
    printer; verify against the actually-printed, re-measured swatches (lot
    system). For profile-accurate CMYK, convert via the print shop's ICC
    profile instead.
    """
    r, g, b = [v / 255.0 for v in rgb]
    k = 1 - max(r, g, b)
    if k >= 1.0:          # pure black
        return (0.0, 0.0, 0.0, 100.0)
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return (round(c * 100, 1), round(m * 100, 1),
            round(y * 100, 1), round(k * 100, 1))

def write_swatch_cmyk(out_path="swatch_cmyk.csv"):

    import csv
    from .template import build_template
    from pipeline.color_correction import THEORETICAL_LAB

    t = build_template()
    # Sort swatches by index so output is in reference order 0..17:
    swatches = sorted(t.swatches, key=lambda s: s.index)

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "group",
                    "R", "G", "B",
                    "C", "M", "Y", "K",
                    "L*", "a*", "b*"])
        for sw in swatches:
            c, m, y, k = _rgb_to_cmyk(sw.nominal_rgb)
            lab = THEORETICAL_LAB[sw.index]
            w.writerow([sw.index+1, sw.group,
                        *sw.nominal_rgb,
                        c, m, y, k,
                        round(float(lab[0]), 2),
                        round(float(lab[1]), 2),
                        round(float(lab[2]), 2)])
    print(f"Wrote {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lot", default="CROMA-v1-LOT-DRAFT")
    ap.add_argument("--out", default="card_draft")
    args = ap.parse_args()

    svg = render_svg(args.lot)
    with open(args.out + ".svg", "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Wrote {args.out}.svg")

    write_swatch_cmyk(args.out + "_cmyk.csv")
    print(f"Wrote cmyk csv")

    try:
        import cairosvg
        cairosvg.svg2pdf(bytestring=svg.encode("utf-8"),
                         write_to=args.out + ".pdf")
        print(f"Wrote {args.out}.pdf")
    except Exception as e:
        print(f"(PDF skipped: {e})")
        print("Open the .svg in a browser and 'Print to PDF' as a fallback.")


if __name__ == "__main__":
    main()