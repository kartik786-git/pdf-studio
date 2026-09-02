"""Security: protect, unlock, watermark, flatten, bates, metadata."""
import os

import fitz

from .base import Job, JobError, open_doc, progress_cb, selected_pages, unique_path


# Protect PDF with user/owner passwords and printing/copying permissions.
def protect(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    user_pw = options.get("user_password", "") or ""
    owner_pw = options.get("owner_password", "") or ""
    if not user_pw and not owner_pw:
        raise JobError("Please enter a user or owner password.")
    perms = 0
    if options.get("allow_printing"):
        perms |= fitz.PDF_PERM_PRINT
    if options.get("allow_copying"):
        perms |= fitz.PDF_PERM_COPY
    if options.get("allow_annotating"):
        perms |= fitz.PDF_PERM_ANNOTATE
    if options.get("allow_modify"):
        perms |= fitz.PDF_PERM_MODIFY
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "protected.pdf")
    doc.save(result, encryption=fitz.PDF_ENCRYPT_AES_256,
             user_pw=user_pw or None, owner_pw=owner_pw or None, permissions=perms,
             garbage=3, deflate=True)
    doc.close()
    return [("protected.pdf", result)]


# Remove password protection and restrictions from a PDF.
def unlock(inputs, options, job: Job):
    src = inputs[0]
    doc = fitz.open(src)
    if doc.needs_pass:
        pw = options.get("password", "")
        if not doc.authenticate(pw):
            raise JobError("Wrong password. Cannot remove the protection.")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "unlocked.pdf")
    doc.save(result, encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
    doc.close()
    return [("unlocked.pdf", result)]


# Add text watermark to PDF (center, tiled, or corner positions).
def watermark(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    text = (options.get("text", "") or "").strip()
    opacity = max(0.0, min(1.0, float(options.get("opacity", 0.2) or 0.2)))
    position = options.get("position", "center")
    try:
        fontsize = max(4, float(options.get("fontsize", 60) or 60))
    except (TypeError, ValueError):
        fontsize = 60
    if not text:
        raise JobError("Please enter watermark text.")
    posmap = {
        "center": (0.5, 0.5),
        "top-left": (0.08, 0.08),
        "top-right": (0.92, 0.08),
        "bottom-left": (0.08, 0.92),
        "bottom-right": (0.92, 0.92),
        "tiled": None,
    }
    anchor = posmap.get(position, (0.5, 0.5))
    pages = selected_pages(options, doc.page_count)
    idxs = range(doc.page_count) if pages is None else pages
    for i in idxs:
        page = doc[i]
        r = page.rect
        shape = page.new_shape()
        if anchor is None:
            fs = max(18, min(48, r.width / 12))
            for xi in range(3):
                for yi in range(3):
                    pt = fitz.Point(r.x0 + (xi + 0.5) * r.width / 3,
                                    r.y0 + (yi + 0.5) * r.height / 3)
                    shape.insert_text(pt, text, fontsize=fs, fontname="helv",
                                      color=(0.6, 0.6, 0.6))
        else:
            tl = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
            x = r.x0 + (r.width - tl) * anchor[0]
            y = r.y0 + (r.height - fontsize) * anchor[1]
            rect = fitz.Rect(x, y, x + tl, y + fontsize)
            shape.draw_rect(rect)
            shape.insert_text(rect.tl, text, fontsize=fontsize, fontname="helv",
                              color=(0, 0, 0))
        shape.finish(color=(0, 0, 0), fill_opacity=opacity, stroke_opacity=opacity)
        shape.commit(overlay=True)
        progress_cb(job, i + 1, doc.page_count)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "watermarked.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("watermarked.pdf", result)]


# Make fillable PDFs read-only, or rasterize everything to flat images.
def flatten(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    mode = options.get("mode", "readonly")
    if mode == "raster":
        out = fitz.open()
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            np = out.new_page(width=pix.width, height=pix.height)
            np.insert_image(np.rect, pixmap=pix)
            progress_cb(job, i + 1, doc.page_count)
        doc.close()
        result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "flattened.pdf")
        out.save(result, garbage=3, deflate=True)
        out.close()
        return [("flattened.pdf", result)]
    changed = False
    for i in range(doc.page_count):
        for w in doc[i].widgets() or []:
            w.field_flags |= fitz.PDF_FIELD_IS_READ_ONLY
            w.update()
            changed = True
        progress_cb(job, i + 1, doc.page_count)
    if not changed:
        raise JobError("No form fields were found to flatten.")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "flattened.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("flattened.pdf", result)]


# Add sequential Bates stamps across multiple documents.
def bates(inputs, options, job: Job):
    doc = fitz.open()
    prefix = options.get("prefix", "") or ""
    suffix = options.get("suffix", "") or ""
    try:
        start = int(options.get("start", 1))
        digits = int(options.get("digits", 4))
    except (TypeError, ValueError):
        raise JobError("Start number and digits must be integers.")
    try:
        fontsize = max(4, float(options.get("fontsize", 10) or 10))
    except (TypeError, ValueError):
        fontsize = 10
    position = options.get("position", "bottom-right")
    num = start
    for path in inputs:
        sub = open_doc(path)
        doc.insert_pdf(sub)
        sub.close()
    pages = selected_pages(options, doc.page_count)
    idxs = range(doc.page_count) if pages is None else pages
    posmap = {
        "top-left": (8, 8),
        "top-right": (None, 8),
        "bottom-left": (8, None),
        "bottom-right": (None, None),
    }
    for i in idxs:
        page = doc[i]
        r = page.rect
        label = f"{prefix}{str(num).zfill(digits)}{suffix}"
        x, y = posmap.get(position, (None, None))
        x = r.x1 - 8 - fitz.get_text_length(label, fontname="helv", fontsize=fontsize) if x is None else x
        y = r.y1 - fontsize - 4 if y is None else y
        page.insert_text(fitz.Point(x, y), label, fontsize=fontsize, fontname="helv")
        num += 1
        progress_cb(job, i + 1, doc.page_count)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "bates.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("bates.pdf", result)]


# Change PDF metadata (title, author, keywords, subject, creator).
def metadata(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    m = doc.metadata or {}
    for key in ("title", "author", "subject", "keywords", "creator", "producer"):
        val = (options.get(key, "") or "").strip()
        if val:
            m[key] = val
    doc.set_metadata(m)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "metadata.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("metadata.pdf", result)]