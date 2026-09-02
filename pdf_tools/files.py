"""Merge, split, extract, delete, organize, alternate-mix."""
import os
import re

import fitz

from .base import (Job, JobError, build_ranges_from_pages, expand_ranges,
                   is_image, is_pdf, open_doc, parse_ranges, progress_cb,
                   safe_filename, unique_path)

OUTDIR = "data"


# Generate a sequential result filename like "document_001.pdf".
def _result_name(src: str, i: int, ext: str = ".pdf") -> str:
    base = os.path.splitext(os.path.basename(src))[0]
    return f"{base}_{i + 1:03d}{ext}"


# Combine multiple PDFs and images into one document.
def merge(inputs, options, job: Job):
    out = fitz.open()
    for path in inputs:
        if is_image(path):
            img = fitz.open(path)
            pix = fitz.Pixmap(img)
            page = out.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, filename=path)
            img.close()
            pix = None
        else:
            doc = open_doc(path)
            out.insert_pdf(doc)
            doc.close()
    if out.page_count == 0:
        raise JobError("No pages to merge.")
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "merged.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("merged.pdf", result)]


# Interleave pages from 2+ documents alternately (page 1 from A, page 1 from B, ...).
def alternate_mix(inputs, options, job: Job):
    docs = [open_doc(p) for p in inputs]
    maxp = max(d.page_count for d in docs)
    out = fitz.open()
    total = maxp * len(docs)
    done = 0
    for pi in range(maxp):
        for d in docs:
            if pi < d.page_count:
                out.insert_pdf(d, from_page=pi, to_page=pi)
            done += 1
            progress_cb(job, done, total)
    for d in docs:
        d.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "alternate.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("alternate.pdf", result)]


# Copy specific pages to a new document (keeps original intact).
def extract_pages(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    ranges = parse_ranges(options.get("ranges", ""), doc.page_count)
    pages = expand_ranges(ranges)
    if len(pages) > doc.page_count:
        raise JobError("Extraction exceeds document size.")
    out = fitz.open()
    for i, p in enumerate(pages):
        out.insert_pdf(doc, from_page=p, to_page=p)
        progress_cb(job, i + 1, len(pages))
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "extracted.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("extracted.pdf", result)]


# Remove specific pages from a PDF (keeps everything else).
def delete_pages(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    ranges = parse_ranges(options.get("ranges", ""), doc.page_count)
    remove = set(expand_ranges(ranges))
    keep = [i for i in range(doc.page_count) if i not in remove]
    if not keep:
        raise JobError("Deleting these pages would leave an empty document.")
    out = fitz.open()
    for i, p in enumerate(keep):
        out.insert_pdf(doc, from_page=p, to_page=p)
        progress_cb(job, i + 1, len(keep))
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "deleted.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("deleted.pdf", result)]


# Parse a single range token like "3" or "1-5" into a list of 0-based page indexes.
def _parse_mixed(part):
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        return list(range(a - 1, b))
    if part.isdigit():
        return [int(part) - 1]
    return None


# Reorder pages based on a spec like "3,1-2,5" — page 3 first, then 1-2, then 5.
def organize(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    spec = options.get("order", "").strip()
    if not spec:
        order = list(range(doc.page_count))
    else:
        order = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            pages = _parse_mixed(part)
            if pages is None:
                raise JobError(f"Invalid order token: {part}")
            order.extend(pages)
        order = [p for p in order if 0 <= p < doc.page_count]
    out = fitz.open()
    for i, p in enumerate(order):
        out.insert_pdf(doc, from_page=p, to_page=p)
        progress_cb(job, i + 1, len(order))
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "organized.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("organized.pdf", result)]


# Split by page ranges or extract every page into separate files.
def split_pages(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    mode = options.get("mode", "ranges")
    out_paths = []
    if mode == "every_page":
        for i in range(doc.page_count):
            out = fitz.open()
            out.insert_pdf(doc, from_page=i, to_page=i)
            p = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), _result_name(src, i))
            out.save(p, garbage=3, deflate=True)
            out.close()
            out_paths.append((_result_name(src, i), p))
            progress_cb(job, i + 1, doc.page_count)
    else:
        ranges = parse_ranges(options.get("ranges", ""), doc.page_count)
        for idx, (a, b) in enumerate(ranges):
            out = fitz.open()
            out.insert_pdf(doc, from_page=a, to_page=b)
            name = f"split_{idx + 1}.pdf"
            p = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), name)
            out.save(p, garbage=3, deflate=True)
            out.close()
            out_paths.append((name, p))
            progress_cb(job, idx + 1, len(ranges))
    doc.close()
    return out_paths


# Split PDF at table-of-contents entries — each chapter becomes a separate file.
def split_bookmarks(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    toc = doc.get_toc()
    level = int(options.get("level", 1))
    chapters = [t for t in toc if t[0] == level]
    if not chapters:
        raise JobError("No bookmarks found at that level.")
    starts = [c[2] - 1 for c in chapters] + [doc.page_count]
    out_paths = []
    for i, (a, b) in enumerate(zip(starts, starts[1:])):
        out = fitz.open()
        out.insert_pdf(doc, from_page=a, to_page=b - 1)
        name = f"{safe_filename(chapters[i][1]) or 'chapter'}.pdf"
        p = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), name)
        out.save(p, garbage=3, deflate=True)
        out.close()
        out_paths.append((name, p))
        progress_cb(job, i + 1, len(chapters))
    doc.close()
    return out_paths


# Split each page in half (left/right or top/bottom) — useful for A3→A4 scans.
def split_half(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    direction = options.get("direction", "vertical")  # vertical = left/right halves
    out = fitz.open()
    for i in range(doc.page_count):
        page = doc[i]
        r = page.rect
        if direction == "vertical":
            half = r.width / 2
            rects = [fitz.Rect(0, 0, half, r.height), fitz.Rect(half, 0, r.width, r.height)]
        else:
            half = r.height / 2
            rects = [fitz.Rect(0, 0, r.width, half), fitz.Rect(0, half, r.width, r.height)]
        for rect in rects:
            np = out.new_page(width=rect.width, height=rect.height)
            np.show_pdf_page(np.rect, doc, i, clip=rect)
        progress_cb(job, i + 1, doc.page_count)
    doc.close()
    result = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), "split_half.pdf")
    out.save(result, garbage=3, deflate=True)
    out.close()
    return [("split_half.pdf", result)]


# Split into files that don't exceed a size limit (e.g., 10MB each).
def split_size(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    budget = float(options.get("size_mb", 10))
    if budget <= 0:
        raise JobError("Size budget must be > 0 MB.")
    tmpdir = os.environ.get("PDF_STUDIO_RESULTS", ".")
    sizes = []
    for i in range(doc.page_count):
        one = fitz.open()
        one.insert_pdf(doc, from_page=i, to_page=i)
        tp = os.path.join(tmpdir, f"_size_p{i}.pdf")
        one.save(tp, garbage=4, deflate=True)
        one.close()
        sizes.append((tp, os.path.getsize(tp)))
        progress_cb(job, i + 1, doc.page_count)
    groups = []
    cur = []
    cur_size = 0
    for i, (tp, sz) in enumerate(sizes):
        if sz > budget * 1024 * 1024 and cur:
            groups.append(cur)
            cur, cur_size = [], 0
        cur.append(i)
        cur_size += sz
        if cur_size >= budget * 1024 * 1024:
            groups.append(cur)
            cur, cur_size = [], 0
    if cur:
        groups.append(cur)
    out_paths = []
    for gi, g in enumerate(groups):
        out = fitz.open()
        for p in g:
            out.insert_pdf(doc, from_page=p, to_page=p)
        name = f"part_{gi + 1}.pdf"
        fp = unique_path(tmpdir, name)
        out.save(fp, garbage=3, deflate=True)
        out.close()
        out_paths.append((name, fp))
    for tp, _ in sizes:
        try:
            os.remove(tp)
        except OSError:
            pass
    doc.close()
    return out_paths


# Split when specific marker text appears on a page (e.g., "Chapter").
def split_text(inputs, options, job: Job):
    src = inputs[0]
    doc = open_doc(src)
    marker = options.get("text", "").strip()
    if not marker:
        raise JobError("Please enter the text that marks a new document.")
    starts = []
    for i in range(doc.page_count):
        text = doc[i].get_text("text") or ""
        if marker.lower() in text.lower():
            starts.append(i)
    if not starts:
        raise JobError(f"Text '{marker}' was not found on any page.")
    if starts[0] != 0:
        starts.insert(0, 0)
    bounds = starts + [doc.page_count]
    out_paths = []
    for idx, (a, b) in enumerate(zip(bounds, bounds[1:])):
        out = fitz.open()
        out.insert_pdf(doc, from_page=a, to_page=b - 1)
        name = f"section_{idx + 1}.pdf"
        fp = unique_path(os.environ.get("PDF_STUDIO_RESULTS", "."), name)
        out.save(fp, garbage=3, deflate=True)
        out.close()
        out_paths.append((name, fp))
        progress_cb(job, idx + 1, len(bounds) - 1)
    doc.close()
    return out_paths