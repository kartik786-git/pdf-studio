"""Compress, deskew, OCR."""
import io
import math
import os

import fitz

from .base import Job, JobError, open_doc, progress_cb, selected_pages, unique_path


# Reduce PDF size by recompressing images and cleaning document structure.
def compress(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        quality = max(5, min(95, int(options.get("quality", 70))))
    except (TypeError, ValueError):
        quality = 70
    try:
        max_dim = max(200, int(options.get("max_dim", 2400)))
    except (TypeError, ValueError):
        max_dim = 2400
    img_xrefs = []
    for i in range(1, doc.xref_length()):
        if doc.xref_get_key(i, "Subtype")[1] == "/Image":
            try:
                info = doc.extract_image(i)
                img_xrefs.append((i, info))
            except Exception:
                pass
    for idx, (xref, info) in enumerate(img_xrefs):
        raw = info["image"]
        ext = info.get("ext", "png")
        img = _to_pil(raw, ext)
        if img is None:
            continue
        w, h = img.size
        scale = min(1.0, max_dim / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), 2)
        tmp = os.path.join(os.environ.get("PDF_STUDIO_RESULTS", "."), "_cimg.jpg")
        try:
            img.save(tmp, format="JPEG", quality=quality, optimize=True)
        except Exception:
            img.convert("RGB").save(tmp, format="JPEG", quality=quality)
        try:
            doc.replace_image(xref, filename=tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        job.update(progress=2 + int(45 * (idx + 1) / max(1, len(img_xrefs))))
    job.update(progress=50, message="Optimizing structure…")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "compressed.pdf")
    doc.save(result, garbage=4, deflate=True, clean=True)
    doc.close()
    before = os.path.getsize(src)
    after = os.path.getsize(result)
    return [("compressed.pdf", result)]


# Convert raw image bytes to a PIL Image (RGB).
def _to_pil(raw, ext):
    try:
        from PIL import Image
        import io as _io
        return Image.open(_io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


# Auto-straighten skewed scanned pages by estimating and correcting rotation.
def deskew(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    limit = float(options.get("limit", 5))
    try:
        from PIL import Image
    except ImportError:
        raise JobError("Pillow is required for the Deskew tool.")
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
        angle = _estimate_skew(page)
        if angle is None or abs(angle) > 15:
            angle = 0.0
        if abs(angle) <= limit:
            angle = 0.0
        r = page.rect
        np = out.new_page(width=r.width, height=r.height)
        if angle:
            zoom = 3
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img = img.rotate(-angle, expand=False, fillcolor=(255, 255, 255))
            tmp = os.path.join(tmpdir, f"_deskew_{i}.png")
            img.save(tmp)
            np.insert_image(np.rect, filename=tmp)
            try:
                os.remove(tmp)
            except OSError:
                pass
        else:
            np.show_pdf_page(r, doc, i)
        progress_cb(job, i + 1, doc.page_count)
    doc.close()
    result = unique_path(tmpdir, "deskewed.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("deskewed.pdf", result)]


# Estimate skew from text line geometry; returns degrees, None if no text.
def _estimate_skew(page) -> float | None:
    try:
        d = page.get_text("dict")
        angles = []
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                sp = line.get("spans", [])
                if not sp:
                    continue
                x0, y0 = line["bbox"][0], line["bbox"][1]
                x1, y1 = line["bbox"][2], line["bbox"][3]
                dx, dy = x1 - x0, y1 - y0
                if abs(dx) < 2:
                    continue
                angles.append(math.degrees(math.atan2(dy, dx)))
        if not angles:
            return None
        import statistics
        return statistics.median(angles)
    except Exception:
        return None


# Make scanned PDFs searchable using RapidOCR (offline, no Tesseract).
def ocr(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    except ImportError:
        raise JobError("rapidocr_onnxruntime not installed. Run: pip install rapidocr_onnxruntime")
    try:
        dpi = max(150, min(300, int(options.get("dpi", 200))))
    except (TypeError, ValueError):
        dpi = 200
    zoom = dpi / 72
    total = doc.page_count
    for i in range(total):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        import numpy as np
        samples = pix.samples
        n = pix.n
        if pix.alpha:
            data = np.frombuffer(samples, dtype=np.uint8).reshape(pix.height, pix.width, n)
            data = data[..., :3]
        else:
            data = np.frombuffer(samples, dtype=np.uint8).reshape(pix.height, pix.width, n)
        result, _ = engine(data)
        if result:
            page = doc[i]
            for box, text, _score in result:
                x0, y0 = box[0][0] / zoom, box[0][1] / zoom
                x1, y1 = box[2][0] / zoom, box[2][1] / zoom
                fontsize = max(2, (y1 - y0))
                if not text or not text.strip():
                    continue
                page.insert_text(fitz.Point(x0, y0), text, fontsize=fontsize,
                                 fontname="helv", render_mode=3, overlay=True)
        progress_cb(job, i + 1, total)
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "ocr.pdf")
    doc.save(result, garbage=3, deflate=True)
    doc.close()
    return [("ocr.pdf", result)]