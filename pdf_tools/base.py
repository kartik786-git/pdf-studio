"""Shared helpers for pdf_tools."""
import os
import re

import fitz

from services.jobs import Job, JobError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
PDF_EXTS = {".pdf"}


# Check if a file path has an image extension.
def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


# Check if a file path has a PDF extension.
def is_pdf(path: str) -> bool:
    return os.path.splitext(path)[1].lower() == ".pdf"


# Open a PDF document, handling password protection.
def open_doc(path: str, password: str = "") -> fitz.Document:
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            raise JobError("The PDF is password-protected. Please provide the password.")
    return doc


# Parse '1-3,5,8-10' into a list of inclusive page-index ranges (0-based).
def parse_ranges(spec: str, total: int) -> list[list[int]]:
    if not spec or not spec.strip():
        raise JobError("Please enter a page range, e.g. 1-3,5,8-10")
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            ranges.append([a - 1, b - 1])
        elif part.isdigit():
            p = int(part)
            ranges.append([p - 1, p - 1])
        else:
            raise JobError(f"Invalid page range token: {part}")
    for a, b in ranges:
        if a < 0 or b >= total:
            raise JobError(f"Page range {a + 1}-{b + 1} is outside the document (1-{total}).")
    return ranges


# Expand page ranges into a flat list of page indices.
def expand_ranges(ranges: list[list[int]]) -> list[int]:
    out = []
    for a, b in ranges:
        out.extend(range(a, b + 1))
    return out


# Resolve an optional `pages` option into a sorted list of 0-based indices.
# Returns None when `pages` is empty/absent (meaning "all pages").
def selected_pages(options: dict, total: int) -> list[int] | None:
    spec = str(options.get("pages") or "").strip()
    if not spec:
        return None
    ranges = parse_ranges(spec, total)
    pages = sorted(set(expand_ranges(ranges)))
    if not pages:
        raise JobError("No pages selected.")
    return pages


# Convert a sorted list of 0-based page indexes into contiguous ranges.
def build_ranges_from_pages(pages: list[int]) -> list[list[int]]:
    if not pages:
        return []
    pages = sorted(set(pages))
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append([start, prev])
            start = prev = p
    ranges.append([start, prev])
    return ranges


# Generate a unique file path by appending a counter if needed.
def unique_path(dirpath: str, name: str) -> str:
    base, ext = os.path.splitext(name)
    p = os.path.join(dirpath, name)
    i = 1
    while os.path.exists(p):
        p = os.path.join(dirpath, f"{base}_{i}{ext}")
        i += 1
    return p


# Return base filename with optional suffix.
def default_name(path: str, suffix: str = "") -> str:
    return f"{os.path.splitext(os.path.basename(path))[0]}{suffix}"


# Sanitize text for use as a filename.
def safe_filename(text: str, fallback: str = "document") -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n]+', " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    return (text or fallback)[:120]


# Update job progress with percentage and message.
def progress_cb(job: Job, done: int, total: int, message: str = "Processing"):
    if total > 0:
        job.update(progress=2 + int(90 * done / total), message=f"{message}… {done}/{total}")