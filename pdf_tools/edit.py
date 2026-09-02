"""PDF editor backend: flatten canvas overlays (text, shapes, images, signatures)."""
import json
import os

import fitz

from .base import Job, JobError, open_doc, progress_cb, unique_path

HELVETICA = "helv"


# inputs[0] = pdf path, inputs[1] = json overlay path (optional).
#
# Overlay format (one dict per page):
#   { "page": 0,
#     "items": [
#        {"type":"text","x":..,"y":..,"size":..,"text":"..","color":"#rrggbb","font":"helv","bold":false},
#        {"type":"rect","x":..,"y":..,"w":..,"h":..,"color":"#..","fill":"#..","width":2},
#        {"type":"ellipse","x":..,"y":..,"w":..,"h":..,"color":"#..","fill":"#..","width":2},
#        {"type":"line","x1":..,"y1":..,"x2":..,"y2":..,"color":"#..","width":2},
#        {"type":"ink","points":[[x,y],...],"color":"#..","width":3},
#        {"type":"image","x":..,"y":..,"w":..,"h":..,"path":"abs path to image"},
#     ]}
# Coordinates are in PDF points from the top-left.
def apply_overlays(inputs, options, job: Job):
    pdf_path = inputs[0]
    overlay_path = inputs[1] if len(inputs) > 1 else None
    items_by_page = {}
    if overlay_path and os.path.exists(overlay_path):
        with open(overlay_path, "r", encoding="utf-8") as f:
            overlay = json.load(f)
        for entry in overlay if isinstance(overlay, list) else []:
            if not isinstance(entry, dict) or "page" not in entry:
                continue
            items_by_page.setdefault(int(entry["page"]), []).extend(entry.get("items", []))

    doc = open_doc(pdf_path)
    for pi in range(doc.page_count):
        page = doc[pi]
        items = items_by_page.get(pi, [])
        if not items:
            continue
        for it in items:
            _draw_item(page, it)
        progress_cb(job, pi + 1, doc.page_count)
    if not any(items_by_page.values()):
        raise JobError("No overlay items were provided.")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "edited.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("edited.pdf", result)]


# Convert hex color string "#rrggbb" to RGB tuple (0-1 range).
def _color(hexstr, default=(0, 0, 0)):
    if not hexstr or not isinstance(hexstr, str):
        return default
    try:
        hexstr = hexstr.lstrip("#")
        return (int(hexstr[0:2], 16) / 255, int(hexstr[2:4], 16) / 255, int(hexstr[4:6], 16) / 255)
    except Exception:
        return default


# Draw a single overlay item (text, rect, ellipse, line, ink, image, highlight) on a page.
def _draw_item(page, it):
    t = it.get("type", "text")
    color = _color(it.get("color"))
    if t == "text":
        x, y = float(it.get("x", 0)), float(it.get("y", 0))
        size = max(4, float(it.get("size", 14) or 14))
        font = it.get("font", HELVETICA)
        if font not in ("helv", "hebo", "tiro", "tibo", "cour"):
            font = HELVETICA
        if it.get("bold") and font == HELVETICA:
            font = "hebo"
        page.insert_text(fitz.Point(x, y), str(it.get("text", "")),
                         fontsize=size, fontname=font, color=color)
    elif t == "rect":
        rect = fitz.Rect(float(it.get("x", 0)), float(it.get("y", 0)),
                         float(it.get("x", 0)) + float(it.get("w", 50)),
                         float(it.get("y", 0)) + float(it.get("h", 50)))
        fill = _color(it.get("fill"))
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=color, fill=fill, width=max(0.5, float(it.get("width", 1) or 1)))
        shape.commit(overlay=True)
    elif t == "ellipse":
        rect = fitz.Rect(float(it.get("x", 0)), float(it.get("y", 0)),
                         float(it.get("x", 0)) + float(it.get("w", 50)),
                         float(it.get("y", 0)) + float(it.get("h", 50)))
        fill = _color(it.get("fill"))
        shape = page.new_shape()
        shape.draw_oval(rect)
        shape.finish(color=color, fill=fill, width=max(0.5, float(it.get("width", 1) or 1)))
        shape.commit(overlay=True)
    elif t == "line":
        shape = page.new_shape()
        shape.draw_line(fitz.Point(float(it.get("x1", 0)), float(it.get("y1", 0))),
                        fitz.Point(float(it.get("x2", 0)), float(it.get("y2", 0))))
        shape.finish(color=color, width=max(0.5, float(it.get("width", 1) or 1)))
        shape.commit(overlay=True)
    elif t == "ink":
        pts = [fitz.Point(float(p[0]), float(p[1])) for p in (it.get("points") or [])]
        if len(pts) >= 2:
            shape = page.new_shape()
            shape.draw_polyline(pts)
            shape.finish(color=color, width=max(0.5, float(it.get("width", 2) or 2)))
            shape.commit(overlay=True)
    elif t == "image":
        img = it.get("path")
        if img and os.path.exists(img):
            rect = fitz.Rect(float(it.get("x", 0)), float(it.get("y", 0)),
                             float(it.get("x", 0)) + float(it.get("w", 100)),
                             float(it.get("y", 0)) + float(it.get("h", 100)))
            page.insert_image(rect, filename=img, overlay=True)
    elif t == "highlight":
        rect = fitz.Rect(float(it.get("x", 0)), float(it.get("y", 0)),
                         float(it.get("x", 0)) + float(it.get("w", 50)),
                         float(it.get("y", 0)) + float(it.get("h", 50)))
        hl = page.add_highlight_annot(rect)
        hl.set_colors(stroke=color or (1, 0.8, 0.2))
        hl.set_opacity(0.4)
        hl.update()


# Render pages to PNG previews for the editor UI.
def render_preview(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        dpi = max(72, min(300, int(options.get("dpi", 100))))
    except (TypeError, ValueError):
        dpi = 100
    zoom = dpi / 72
    out = []
    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        w, h = int(round(page.rect.width)), int(round(page.rect.height))
        name = f"preview_{i}_{w}x{h}.png"
        path = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), name)
        pix.save(path)
        out.append((name, path))
        progress_cb(job, i + 1, doc.page_count)
    doc.close()
    return out