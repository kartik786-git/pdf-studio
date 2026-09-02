"""Tool registry: name -> metadata + handler."""
from . import convert, edit, files, misc, pages, scan, security

CATEGORIES = [
    {"id": "files", "name": "Files", "desc": "Merge, split and organize documents"},
    {"id": "pages", "name": "Pages", "desc": "Rotate, crop, resize and clean up pages"},
    {"id": "edit", "name": "Edit & Sign", "desc": "Edit PDFs, add text, images and signatures"},
    {"id": "convert", "name": "Convert", "desc": "Convert to and from PDF"},
    {"id": "scan", "name": "Compress & Scans", "desc": "Compress, deskew and OCR"},
    {"id": "security", "name": "Security", "desc": "Protect, unlock, watermark and more"},
    {"id": "misc", "name": "Others", "desc": "Page numbers, metadata, repair and more"},
]


# Create a text input parameter schema.
def _text(name, label, default="", placeholder=""):
    return {"type": "text", "name": name, "label": label, "default": default, "placeholder": placeholder}


# Create a select dropdown parameter schema.
def _select(name, label, options, default=None):
    return {"type": "select", "name": name, "label": label, "options": options,
            "default": default if default is not None else options[0]}


# Create a numeric input parameter schema.
def _num(name, label, default, min=0, max=1000, step=1):
    return {"type": "number", "name": name, "label": label, "default": default,
            "min": min, "max": max, "step": step}


# Create a checkbox parameter schema.
def _check(name, label, default=False):
    return {"type": "checkbox", "name": name, "label": label, "default": default}


# Create a pages range text input parameter schema.
def _pages(default=""):
    return _text("pages", "Pages (blank = all)", default, "1-3,5,8")


TOOLS = {
    # ------------------------------ Files ------------------------------
    "merge": {
        "category": "files", "name": "Merge", "accept": "pdf,image", "multi": True,
        "desc": "Combine multiple PDFs and images into one document",
        "params": [_text("name", "Output name (optional)", "merged", "merged")],
        "handler": files.merge,
    },
    "alternate_mix": {
        "category": "files", "name": "Alternate & Mix", "accept": "pdf", "multi": True,
        "desc": "Mixes pages from 2 or more documents, alternating between them",
        "params": [],
        "handler": files.alternate_mix,
    },
    "organize": {
        "category": "files", "name": "Organize", "accept": "pdf", "multi": False,
        "desc": "Arrange and reorder PDF pages. Example: 3,1-2,5",
        "params": [_text("order", "New page order", "", "e.g. 3,1-2,5")],
        "handler": files.organize,
    },
    "split_pages": {
        "category": "files", "name": "Split", "accept": "pdf", "multi": False,
        "desc": "Split specific page ranges or extract every page into a separate document",
        "params": [
            _select("mode", "Mode", [("ranges", "Split by ranges"), ("every_page", "Extract every page")]),
            _text("ranges", "Page ranges (ranges mode)", "", "1-3,5,8-10"),
        ],
        "handler": files.split_pages,
    },
    "split_bookmarks": {
        "category": "files", "name": "Split by Bookmarks", "accept": "pdf", "multi": False,
        "desc": "Extract chapters into separate documents based on the table of contents",
        "params": [_select("level", "Bookmark level", [("1", "Level 1 (top)"), ("2", "Level 2")])],
        "handler": files.split_bookmarks,
    },
    "split_half": {
        "category": "files", "name": "Split in Half", "accept": "pdf", "multi": False,
        "desc": "Split two-page layout scans: A3 to double A4 or A4 to double A5",
        "params": [_select("direction", "Direction", [("vertical", "Vertical (left/right)"), ("horizontal", "Horizontal (top/bottom)")])],
        "handler": files.split_half,
    },
    "split_size": {
        "category": "files", "name": "Split by Size", "accept": "pdf", "multi": False,
        "desc": "Get multiple smaller documents with a specific file size",
        "params": [_num("size_mb", "Max size per part (MB)", 10, 1, 1024)],
        "handler": files.split_size,
    },
    "split_text": {
        "category": "files", "name": "Split by Text", "accept": "pdf", "multi": False,
        "desc": "Extract separate documents when specific text appears on a page",
        "params": [_text("text", "Marker text", "", "e.g. 'Chapter'")],
        "handler": files.split_text,
    },
    "extract_pages": {
        "category": "files", "name": "Extract Pages", "accept": "pdf", "multi": False,
        "desc": "Get a new document containing only the desired pages",
        "params": [_text("ranges", "Pages to extract", "", "1-3,5")],
        "handler": files.extract_pages,
    },
    "delete_pages": {
        "category": "files", "name": "Delete Pages", "accept": "pdf", "multi": False,
        "desc": "Remove pages from a PDF document",
        "params": [_text("ranges", "Pages to remove", "", "1-3,5")],
        "handler": files.delete_pages,
    },
    # ------------------------------ Pages ------------------------------
    "rotate": {
        "category": "pages", "name": "Rotate", "accept": "pdf", "multi": False,
        "desc": "Rotate and save PDF pages permanently",
        "params": [_select("angle", "Angle", [("90", "90° clockwise"), ("180", "180°"), ("270", "270° clockwise")]),
                   _pages()],
        "handler": pages.rotate,
    },
    "crop": {
        "category": "pages", "name": "Crop", "accept": "pdf", "multi": False,
        "desc": "Trim PDF margins, change PDF page size",
        "params": [
            _num("left", "Left margin (pt)", 0, 0, 1000),
            _num("right", "Right margin (pt)", 0, 0, 1000),
            _num("top", "Top margin (pt)", 0, 0, 1000),
            _num("bottom", "Bottom margin (pt)", 0, 0, 1000),
            _pages(),
        ],
        "handler": pages.crop,
    },
    "resize": {
        "category": "pages", "name": "Resize", "accept": "pdf", "multi": False,
        "desc": "Add page margins and padding, change PDF page size",
        "params": [
            _select("size", "Page size", [("A4", "A4"), ("A3", "A3"), ("A5", "A5"),
                                          ("Letter", "Letter"), ("Legal", "Legal"), ("custom", "Custom")]),
            _num("width", "Width (pt, custom)", 595, 50, 5000),
            _num("height", "Height (pt, custom)", 842, 50, 5000),
            _num("margin", "Margin / padding (pt)", 0, 0, 1000),
        ],
        "handler": pages.resize,
    },
    "flip": {
        "category": "pages", "name": "Flip", "accept": "pdf", "multi": False,
        "desc": "Mirror pages horizontally or vertically",
        "params": [_select("direction", "Direction", [("horizontal", "Horizontal (left-right)"), ("vertical", "Vertical (top-bottom)")]),
                   _pages()],
        "handler": pages.flip,
    },
    "nup": {
        "category": "pages", "name": "N-up", "accept": "pdf", "multi": False,
        "desc": "Print multiple pages per sheet (2-up, 4-up…)",
        "params": [
            _num("cols", "Columns", 2, 1, 8),
            _num("rows", "Rows", 2, 1, 8),
            _num("gap", "Gap (pt)", 4, 0, 50),
        ],
        "handler": pages.nup,
    },
    "grayscale": {
        "category": "pages", "name": "Grayscale", "accept": "pdf", "multi": False,
        "desc": "Make a PDF text and images grayscale",
        "params": [],
        "handler": pages.grayscale,
    },
    "remove_annotations": {
        "category": "pages", "name": "Remove Annotations", "accept": "pdf", "multi": False,
        "desc": "Batch remove highlights, strikeouts or any other annotations",
        "params": [_select("mode", "Remove", [("all", "All annotations"), ("markup", "Markup (highlight/underline/etc.)")]),
                   _pages()],
        "handler": pages.remove_annotations,
    },
    # ------------------------------ Edit & Sign ------------------------------
    "editor": {
        "category": "edit", "name": "PDF Editor", "accept": "pdf", "multi": False,
        "desc": "Edit PDF files: add text, images, shapes, drawings and signatures",
        "params": [], "editor": True,
        "handler": edit.apply_overlays,
    },
    "create_forms": {
        "category": "edit", "name": "Create Forms", "accept": "pdf", "multi": False,
        "desc": "Make the first PDF page fillable with text fields (JSON)",
        "params": [
            _text("fields_json", "Field JSON", "",
                  '[{"page":1,"x":60,"y":80,"w":160,"h":18,"name":"name","value":""}]'),
        ],
        "handler": misc.create_forms,
    },
    # ------------------------------ Convert ------------------------------
    "pdf_to_text": {
        "category": "convert", "name": "PDF to Text", "accept": "pdf", "multi": False,
        "desc": "Extract all text from a PDF document to a text file",
        "params": [_select("mode", "Mode", [("plain", "Plain text"), ("layout", "Layout text")])],
        "handler": convert.pdf_to_text,
    },
    "pdf_to_jpg": {
        "category": "convert", "name": "PDF to JPG", "accept": "pdf", "multi": False,
        "desc": "Convert PDF pages to JPG images",
        "params": [_num("dpi", "Resolution (DPI)", 150, 72, 600, 10)],
        "handler": convert.pdf_to_jpg,
    },
    "pdf_to_png": {
        "category": "convert", "name": "PDF to PNG", "accept": "pdf", "multi": False,
        "desc": "Convert PDF pages to PNG images",
        "params": [_num("dpi", "Resolution (DPI)", 150, 72, 600, 10)],
        "handler": convert.pdf_to_png,
    },
    "pdf_to_word": {
        "category": "convert", "name": "PDF to Word", "accept": "pdf", "multi": False,
        "desc": "Convert from PDF to DOC (requires pdf2docx)",
        "params": [],
        "handler": convert.pdf_to_word,
    },
    "pdf_to_excel": {
        "category": "convert", "name": "PDF to Excel", "accept": "pdf", "multi": False,
        "desc": "Extract table data from PDF to Excel or CSV",
        "params": [_select("format", "Format", [("xlsx", "Excel (.xlsx)"), ("csv", "CSV (.csv)")])],
        "handler": convert.pdf_to_excel,
    },
    "pdf_to_ppt": {
        "category": "convert", "name": "PDF to PPT", "accept": "pdf", "multi": False,
        "desc": "Convert PDF pages to a PowerPoint presentation",
        "params": [],
        "handler": convert.pdf_to_ppt,
    },
    "jpg_to_pdf": {
        "category": "convert", "name": "JPG to PDF", "accept": "image", "multi": True,
        "desc": "Convert images to a PDF (one page per image)",
        "params": [_text("name", "Output name", "images", "images")],
        "handler": convert.images_to_pdf,
    },
    "html_to_pdf": {
        "category": "convert", "name": "HTML to PDF", "accept": "html", "multi": False,
        "desc": "Convert HTML files to PDF documents",
        "params": [],
        "handler": convert.html_to_pdf,
    },
    "word_to_pdf": {
        "category": "convert", "name": "Word/PPT/Excel to PDF", "accept": "office", "multi": False,
        "desc": "Convert DOCX/PPTX/XLSX to PDF (requires LibreOffice)",
        "params": [_text("soffice", "soffice.exe path (optional)", "", "C:\\Program Files\\LibreOffice\\program\\soffice.exe")],
        "handler": convert.office_to_pdf,
    },
    "extract_images": {
        "category": "convert", "name": "Extract Images", "accept": "pdf", "multi": False,
        "desc": "Extract all embedded images from a PDF",
        "params": [],
        "handler": convert.extract_images,
    },
    # ------------------------------ Compress & Scans ------------------------------
    "compress": {
        "category": "scan", "name": "Compress", "accept": "pdf", "multi": False,
        "desc": "Reduce the size of your PDF (recompresses images, cleans structure)",
        "params": [
            _num("quality", "Image quality", 70, 5, 95),
            _num("max_dim", "Max image dimension (px)", 2400, 200, 8000, 100),
        ],
        "handler": scan.compress,
    },
    "deskew": {
        "category": "scan", "name": "Deskew", "accept": "pdf", "multi": False,
        "desc": "Automatically straighten and deskew scanned PDF pages",
        "params": [_num("limit", "Max correction angle (°)", 5, 0, 15, 0.5),
                   _pages()],
        "handler": scan.deskew,
    },
    "ocr": {
        "category": "scan", "name": "OCR", "accept": "pdf", "multi": False,
        "desc": "Convert PDF scans to searchable text (RapidOCR, offline)",
        "params": [_num("dpi", "Scan resolution (DPI)", 200, 150, 300, 10)],
        "handler": scan.ocr,
    },
    # ------------------------------ Security ------------------------------
    "protect": {
        "category": "security", "name": "Protect", "accept": "pdf", "multi": False,
        "desc": "Protect the file with a password and permissions",
        "params": [
            _text("user_password", "User password (to open)", "", "password"),
            _text("owner_password", "Owner password (to edit)", "", "password"),
            _check("allow_printing", "Allow printing", True),
            _check("allow_copying", "Allow copying text", True),
            _check("allow_annotating", "Allow annotating", False),
            _check("allow_modify", "Allow modifying", False),
        ],
        "handler": security.protect,
    },
    "unlock": {
        "category": "security", "name": "Unlock", "accept": "pdf", "multi": False,
        "desc": "Remove restrictions and password from PDF files",
        "params": [_text("password", "Password (if protected)", "", "")],
        "handler": security.unlock,
    },
    "watermark": {
        "category": "security", "name": "Watermark", "accept": "pdf", "multi": False,
        "desc": "Add text watermark to PDF documents",
        "params": [
            _text("text", "Watermark text", "", "CONFIDENTIAL"),
            _num("opacity", "Opacity", 0.2, 0.05, 1, 0.05),
            _num("fontsize", "Font size", 60, 8, 300),
            _select("position", "Position", [("center", "Center"), ("tiled", "Tiled"),
                                             ("top-left", "Top left"), ("top-right", "Top right"),
                                             ("bottom-left", "Bottom left"), ("bottom-right", "Bottom right")]),
            _pages(),
        ],
        "handler": security.watermark,
    },
    "flatten": {
        "category": "security", "name": "Flatten", "accept": "pdf", "multi": False,
        "desc": "Makes fillable PDFs read-only, or rasterizes everything",
        "params": [_select("mode", "Mode", [("readonly", "Make fields read-only"), ("raster", "Rasterize (flatten fully)")])],
        "handler": security.flatten,
    },
    "bates": {
        "category": "security", "name": "Bates Numbering", "accept": "pdf", "multi": True,
        "desc": "Bates stamp multiple files at once",
        "params": [
            _text("prefix", "Prefix", "", "e.g. CASE-"),
            _num("start", "Start number", 1, 1, 9999999),
            _num("digits", "Digits", 4, 1, 10),
            _text("suffix", "Suffix", "", ""),
            _select("position", "Position", [("bottom-right", "Bottom right"), ("bottom-left", "Bottom left"),
                                             ("top-right", "Top right"), ("top-left", "Top left")]),
            _pages(),
        ],
        "handler": security.bates,
    },
    "metadata": {
        "category": "security", "name": "Edit Metadata", "accept": "pdf", "multi": False,
        "desc": "Change PDF author, title, keywords, subject and other metadata",
        "params": [
            _text("title", "Title", ""), _text("author", "Author", ""),
            _text("subject", "Subject", ""), _text("keywords", "Keywords", ""),
            _text("creator", "Creator", ""),
        ],
        "handler": security.metadata,
    },
    # ------------------------------ Misc ------------------------------
    "page_numbers": {
        "category": "misc", "name": "Page Numbers", "accept": "pdf", "multi": False,
        "desc": "Add PDF page numbers",
        "params": [
            _num("start", "Start number", 1, 1, 9999),
            _num("fontsize", "Font size", 12, 4, 100),
            _select("format", "Format", [("plain", "1, 2, 3…"), ("page_of_total", "1 / N"), ("roman", "i, ii, iii…")]),
            _select("position", "Position", [("bottom-center", "Bottom center"), ("bottom-left", "Bottom left"),
                                             ("bottom-right", "Bottom right"), ("top-center", "Top center"),
                                             ("top-left", "Top left"), ("top-right", "Top right")]),
            _pages(),
        ],
        "handler": misc.page_numbers,
    },
    "header_footer": {
        "category": "misc", "name": "Header & Footer", "accept": "pdf", "multi": False,
        "desc": "Apply page numbers or text labels to PDF files",
        "params": [
            _text("text", "Text", "", "e.g. Draft 2026"),
            _num("fontsize", "Font size", 11, 4, 100),
            _num("margin", "Margin (pt)", 36, 4, 300),
            _select("where", "Position", [("header", "Header (top)"), ("footer", "Footer (bottom)")]),
            _select("align", "Alignment", [("center", "Center"), ("left", "Left"), ("right", "Right")]),
            _pages(),
        ],
        "handler": misc.header_footer,
    },
    "rename": {
        "category": "misc", "name": "Rename", "accept": "pdf", "multi": False,
        "desc": "Change document filename based on text from the PDF pages",
        "params": [_num("words", "Words from first page", 6, 1, 30)],
        "handler": misc.rename,
    },
    "repair": {
        "category": "misc", "name": "Repair", "accept": "pdf", "multi": False,
        "desc": "Recover data from a corrupted or damaged PDF document",
        "params": [],
        "handler": misc.repair,
    },
    "create_bookmarks": {
        "category": "misc", "name": "Create Bookmarks", "accept": "pdf", "multi": False,
        "desc": "Create PDF bookmarks from matching text lines",
        "params": [_text("pattern", "Heading regex", r"^.{4,80}$", r"^.{4,80}$")],
        "handler": misc.create_bookmarks,
    },
}


# Serializable registry for the frontend.
def schema():
    out = []
    for tid, t in TOOLS.items():
        out.append({
            "id": tid,
            "category": t["category"],
            "name": t["name"],
            "desc": t["desc"],
            "accept": t["accept"],
            "multi": t["multi"],
            "editor": t.get("editor", False),
            "params": t["params"],
        })
    return out


# Retrieve tool metadata by ID.
def get(tid: str):
    return TOOLS.get(tid)