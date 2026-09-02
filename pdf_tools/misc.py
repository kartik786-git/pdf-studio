"""Misc: page numbers, header & footer, rename, repair, bookmarks, forms."""
import os
import re

import fitz

from .base import (Job, JobError, open_doc, progress_cb, safe_filename,
                   selected_pages, unique_path)


# Add page numbers to each page (plain, x/N, or roman numerals).
def page_numbers(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    position = options.get("position", "bottom-center")
    fmt = options.get("format", "plain")
    try:
        start = int(options.get("start", 1))
        fontsize = max(4, float(options.get("fontsize", 12) or 12))
    except (TypeError, ValueError):
        raise JobError("Start number and font size must be numbers.")
    posmap = {
        "top-left": (0.08, 0.03),
        "top-center": (0.5, 0.03),
        "top-right": (0.92, 0.03),
        "bottom-left": (0.08, 0.96),
        "bottom-center": (0.5, 0.96),
        "bottom-right": (0.92, 0.96),
    }
    total = doc.page_count
    pages = selected_pages(options, total)
    idxs = range(total) if pages is None else pages
    for i in idxs:
        page = doc[i]
        r = page.rect
        n = i + start
        if fmt == "roman":
            label = _to_roman(n).lower()
        elif fmt == "page_of_total":
            label = f"{i + 1} / {total}"
        else:
            label = str(n)
        xf, yf = posmap.get(position, (0.5, 0.96))
        tl = fitz.get_text_length(label, fontname="helv", fontsize=fontsize)
        x = r.x0 + (r.width - tl) * xf
        y = r.y0 + r.height * yf
        page.insert_text(fitz.Point(x, y), label, fontsize=fontsize, fontname="helv")
        progress_cb(job, i + 1, total)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "numbered.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("numbered.pdf", result)]


# Convert integer to Roman numeral string.
def _to_roman(n: int) -> str:
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
            (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
            (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out


# Add text labels to the header or footer of each page.
def header_footer(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    text = (options.get("text", "") or "").strip()
    where = options.get("where", "footer")
    align = options.get("align", "center")
    try:
        fontsize = max(4, float(options.get("fontsize", 11) or 11))
        margin = max(4, float(options.get("margin", 36) or 36))
    except (TypeError, ValueError):
        raise JobError("Font size and margin must be numbers.")
    if not text:
        raise JobError("Please enter the header/footer text.")
    total = doc.page_count
    pages = selected_pages(options, total)
    idxs = range(total) if pages is None else pages
    for i in idxs:
        page = doc[i]
        r = page.rect
        tl = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
        if align == "left":
            x = r.x0 + margin
        elif align == "right":
            x = r.x1 - margin - tl
        else:
            x = r.x0 + (r.width - tl) / 2
        y = r.y0 + margin if where == "header" else r.y1 - margin
        page.insert_text(fitz.Point(x, y), text, fontsize=fontsize, fontname="helv")
        progress_cb(job, i + 1, total)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "hdr_ftr.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("hdr_ftr.pdf", result)]


# Rename file based on text content from the first page.
def rename(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    text = (doc[0].get_text("text") or "").strip() if doc.page_count else ""
    doc.close()
    words = text.split()
    n = int(options.get("words", 6) or 6)
    name = safe_filename(" ".join(words[:n])) if words else "document"
    name = name if name.lower().endswith(".pdf") else name + ".pdf"
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), name)
    import shutil
    shutil.copyfile(src, result)
    return [(name, result)]


# Recover data from a corrupted or damaged PDF (tries pypdf then PyMuPDF).
def repair(inputs, options, job: Job):
    src = inputs[0]
    out = None
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(src, strict=False)
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "repaired.pdf")
        with open(result, "wb") as f:
            writer.write(f)
        out = result
    except Exception as e:
        try:
            doc = fitz.open(src)
            result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "repaired.pdf")
            doc.save(result, garbage=4, deflate=True, clean=True)
            doc.close()
            out = result
        except Exception as e2:
            raise JobError(f"Could not repair the file: {e} / {e2}")
    return [("repaired.pdf", out)]


# Create PDF bookmarks/TOC from matching text lines (regex pattern).
def create_bookmarks(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    pattern = options.get("pattern", r"^.{4,80}$")
    toc = []
    total = doc.page_count
    for i in range(total):
        page = doc[i]
        for line in (page.get_text("text") or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(pattern, line) and len(line) <= 200:
                toc.append([1, line, i + 1])
        progress_cb(job, i + 1, total)
    if not toc:
        raise JobError("No matching heading lines were found for bookmarks.")
    doc.set_toc(toc)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "bookmarked.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("bookmarked.pdf", result)]


# Build a fillable form: original page as background + ReportLab AcroForm fields.
def create_forms(inputs, options, job: Job):
    src = inputs[0]
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        raise JobError("reportlab not installed.")
    import json
    spec = (options.get("fields_json", "") or "").strip()
    if not spec:
        raise JobError("Enter field definitions as JSON (see format hint).")
    try:
        fields = json.loads(spec)
        assert isinstance(fields, list)
    except Exception:
        raise JobError("Invalid JSON. Use a list of {page, x, y, w, h, name, value} objects.")
    doc = open_doc(src)
    page = doc[0]
    r = page.rect
    pw, ph = r.width, r.height
    dpi = 144  # 2x for crispness
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    bg_img = os.path.join(os.environ.get("PDF_STUDIO_RESULTS", "."), "_bg.png")
    pix.save(bg_img)
    target = os.path.join(os.environ.get("PDF_STUDIO_RESULTS", "."), "_form_layer.pdf")
    c = canvas.Canvas(target, pagesize=(pw, ph))
    c.drawImage(bg_img, 0, 0, width=pw, height=ph)
    for f in fields:
        name = str(f.get("name", "field"))
        x, y = float(f.get("x", 50)), float(f.get("y", 50))
        w, h = float(f.get("w", 120)), float(f.get("h", 18))
        value = f.get("value", "") or ""
        c.acroForm.textfield(name=name, x=x, y=ph - y - h, width=w, height=h,
                             value=str(value), borderStyle="solid", fontSize=10,
                             fontName="Helvetica")
    c.showPage()
    c.save()
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "form.pdf")
    import shutil
    shutil.move(target, result)
    for tmp in (bg_img,):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return [("form.pdf", result)]