"""Page operations: rotate, crop, resize, flip, n-up, grayscale, remove annotations."""
import os

import fitz

from .base import Job, JobError, open_doc, progress_cb, selected_pages, unique_path

PAGE_SIZES = {
    "A4": (595.0, 842.0),
    "A3": (841.9, 1190.6),
    "A5": (419.5, 595.3),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
}


# Rotate pages by 90°/180°/270°. Uses page.set_rotation() to permanently set the angle.
def rotate(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    angle = int(options.get("angle", 90)) % 360
    pages = selected_pages(options, doc.page_count)
    idxs = range(doc.page_count) if pages is None else pages
    for i in idxs:
        page = doc[i]
        cur = page.rotation
        page.set_rotation((cur + angle) % 360)
        progress_cb(job, i + 1, doc.page_count)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "rotated.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("rotated.pdf", result)]


# Trim margins by setting a crop box. Margins are in PDF points (1pt = 1/72 inch).
def crop(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        left = float(options.get("left", 0))
        right = float(options.get("right", 0))
        top = float(options.get("top", 0))
        bottom = float(options.get("bottom", 0))
    except (TypeError, ValueError):
        raise JobError("Crop margins must be numbers (in points).")
    pages = selected_pages(options, doc.page_count)
    idxs = range(doc.page_count) if pages is None else pages
    for i in idxs:
        page = doc[i]
        r = page.rect
        if left + right >= r.width or top + bottom >= r.height:
            raise JobError("Crop margins exceed page size on page " + str(i + 1))
        page.set_cropbox(fitz.Rect(r.x0 + left, r.y0 + top, r.x1 - right, r.y1 - bottom))
        progress_cb(job, i + 1, doc.page_count)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "cropped.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("cropped.pdf", result)]


# Change page size (A4, A3, Letter, Custom) and add margins. Scales content to fit.
def resize(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    mode = options.get("size", "A4")
    try:
        margin = float(options.get("margin", 0))
    except (TypeError, ValueError):
        margin = 0
    if mode in PAGE_SIZES:
        w, h = PAGE_SIZES[mode]
    else:
        try:
            w = float(options.get("width", 0))
            h = float(options.get("height", 0))
        except (TypeError, ValueError):
            raise JobError("Invalid page size.")
        if w <= 0 or h <= 0:
            raise JobError("Invalid width/height.")
    out = fitz.open()
    total = doc.page_count
    for i in range(total):
        page = doc[i]
        r = page.rect
        avail_w = w - 2 * margin
        avail_h = h - 2 * margin
        if avail_w <= 0 or avail_h <= 0:
            raise JobError("Margin too large for page size.")
        scale = min(avail_w / r.width, avail_h / r.height)
        pw, ph = r.width * scale, r.height * scale
        ox = (w - pw) / 2
        oy = (h - ph) / 2
        np = out.new_page(width=w, height=h)
        np.show_pdf_page(fitz.Rect(ox, oy, ox + pw, oy + ph), doc, i)
        progress_cb(job, i + 1, total)
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "resized.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("resized.pdf", result)]


# Mirror pages horizontally or vertically. Renders to image, flips with Pillow, re-inserts.
def flip(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    direction = options.get("direction", "horizontal")
    try:
        from PIL import Image
    except ImportError:
        raise JobError("Pillow is required for the Flip tool.")
    tmpdir = os.environ.get("PDF_STUDIO_RESULTS", ".")
    out = fitz.open()
    pages = selected_pages(options, doc.page_count)
    for i in range(doc.page_count):
        page = doc[i]
        r = page.rect
        if pages is not None and i not in pages:
            np = out.new_page(width=r.width, height=r.height)
            np.show_pdf_page(r, doc, i)
            progress_cb(job, i + 1, doc.page_count)
            continue
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if direction == "horizontal":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        tmp = os.path.join(tmpdir, f"_flip_{i}.png")
        img.save(tmp)
        np = out.new_page(width=r.width, height=r.height)
        np.insert_image(np.rect, filename=tmp)
        try:
            os.remove(tmp)
        except OSError:
            pass
        progress_cb(job, i + 1, doc.page_count)
    doc.close()
    result = unique_path(tmpdir, "flipped.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("flipped.pdf", result)]


# Place multiple logical pages on each sheet (2-up, 4-up). Useful for printing.
def nup(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        cols = max(1, int(options.get("cols", 2)))
        rows = max(1, int(options.get("rows", 2)))
        gap = max(0, float(options.get("gap", 4)))
    except (TypeError, ValueError):
        raise JobError("Columns/rows must be integers.")
    per = cols * rows
    out = fitz.open()
    total_sheets = -(-doc.page_count // per)
    for si in range(total_sheets):
        idxs = [si * per + j for j in range(per) if si * per + j < doc.page_count]
        sheet_w = max(doc[i].rect.width for i in idxs)
        sheet_h = max(doc[i].rect.height for i in idxs)
        sheet = out.new_page(width=sheet_w * cols + gap * (cols + 1),
                             height=sheet_h * rows + gap * (rows + 1))
        for j in range(per):
            idx = si * per + j
            if idx >= doc.page_count:
                break
            page = doc[idx]
            r = page.rect
            scale = min((sheet_w - gap) / r.width, (sheet_h - gap) / r.height)
            pw, ph = r.width * scale, r.height * scale
            col = j % cols
            row = j // cols
            ox = gap + col * (sheet_w + gap)
            oy = gap + row * (sheet_h + gap)
            sheet.show_pdf_page(fitz.Rect(ox, oy, ox + pw, oy + ph), doc, idx)
        progress_cb(job, si + 1, total_sheets)
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), f"nup_{cols}x{rows}.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [(f"nup_{cols}x{rows}.pdf", result)]


# Convert all colors to shades of gray. Uses convert_colorspace() with rasterize fallback.
def grayscale(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        doc.convert_colorspace(colorspace=fitz.csGRAY, keep_info=True)
    except Exception:  # fallback: rasterize to grayscale
        out = fitz.open()
        for i in range(doc.page_count):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
            np = out.new_page(width=pix.width, height=pix.height)
            np.insert_image(np.rect, pixmap=pix)
            progress_cb(job, i + 1, doc.page_count)
        doc.close()
        result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "grayscale.pdf")
        out.save(result, garbage=3, deflate=True)
        out.close()
        return [("grayscale.pdf", result)]
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "grayscale.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("grayscale.pdf", result)]


# Delete highlights, strikeouts, and other markup annotations.
def remove_annotations(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    mode = options.get("mode", "all")
    pages = selected_pages(options, doc.page_count)
    idxs = range(doc.page_count) if pages is None else pages
    removed = 0
    for i in idxs:
        page = doc[i]
        for a in list(page.annots() or []):
            typ = a.type[1] if a.type else ""
            if mode == "all" or (mode == "markup" and typ in ("Highlight", "Underline",
                                                               "StrikeOut", "Squiggly", "Redact", "Polygon", "PolyLine", "Line", "Square", "Circle", "FreeText", "Text", "Ink")):
                page.delete_annot(a)
                removed += 1
        progress_cb(job, i + 1, doc.page_count)
    if removed == 0:
        raise JobError("No matching annotations were found.")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "clean.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("clean.pdf", result)]