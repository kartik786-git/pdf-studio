"""PDF Studio — offline Sejda-like PDF toolkit."""
import json
import os
import threading
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query, Path
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from pydantic import BaseModel, Field, ConfigDict

import pdf_tools
import services.jobs as jobs
import services.storage as storage

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
RESULTS = os.path.join(HERE, "data", "results")

# ── FastAPI app with Swagger UI at /api ──────────────────────────────
app = FastAPI(
    title="PDF Studio API",
    description=(
        "A complete offline PDF toolkit API. Process PDFs locally with no cloud uploads.\n\n"
        "## Workflow\n"
        "1. **Upload** files via `POST /api/tools/{tool_id}` to get a `job_id`\n"
        "2. **Poll** status via `GET /api/jobs/{job_id}` until status is done\n"
        "3. **Download** result via `GET /api/download/{job_id}`\n\n"
        "## Available Tools (43)\n"
        "- **Files**: Merge, Alternate Mix, Organize, Split, Split Bookmarks, Split Half, "
        "Split Size, Split Text, Extract Pages, Delete Pages\n"
        "- **Pages**: Rotate, Crop, Resize, Flip, N-up, Grayscale, Remove Annotations\n"
        "- **Edit**: PDF Editor (canvas overlay), Create Forms\n"
        "- **Convert**: PDF to Text/JPG/PNG/Word/PPT/Excel, JPG to PDF, HTML to PDF, Extract Images\n"
        "- **Scans**: Compress, Deskew, OCR\n"
        "- **Security**: Protect, Unlock, Watermark, Flatten, Bates Numbering, Edit Metadata\n"
        "- **Others**: Page Numbers, Header/Footer, Rename, Repair, Create Bookmarks"
    ),
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

storage.init()
storage.cleanup_ttl()
os.environ.setdefault("PDF_STUDIO_RESULTS", RESULTS)

ALLOWED = {
    "pdf": {".pdf"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"},
    "html": {".html", ".htm"},
    "office": {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods", ".odp"},
}


# ── Pydantic Models ──────────────────────────────────────────────────

class JobCreated(BaseModel):
    """Response when a tool job is submitted."""
    job_id: str = Field(..., description="Job ID to poll for results", example="abc123def456")


class JobStatus(BaseModel):
    """Response when polling job status."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Job identifier")
    tool: str = Field(..., description="Tool name that was executed")
    status: str = Field(..., description="queued | running | done | error")
    progress: int = Field(..., description="Progress percentage 0-100")
    message: str = Field(..., description="Current status message")
    error: str = Field("", description="Error message if status is error")
    results: list = Field(default_factory=list, description="Output files with name and download URL")
    zipped: bool = Field(default=False, description="True if results are bundled in a ZIP")


class ToolInfo(BaseModel):
    """Schema for a single tool."""
    id: str
    category: str
    name: str
    desc: str
    accept: str
    multi: bool
    editor: bool = False
    params: list = Field(default_factory=list)


class ToolsResponse(BaseModel):
    """Response from GET /api/tools."""
    categories: list = Field(..., description="Category list")
    tools: list = Field(..., description="All tool schemas")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


# ── Startup cleanup ──────────────────────────────────────────────────

# Periodically clean up stale job directories (runs every 15 minutes).
def _startup_cleanup():
    threading.Timer(900, _startup_cleanup).start()
    storage.cleanup_ttl()

threading.Thread(target=_startup_cleanup, daemon=True).start()


# ── Swagger / ReDoc at /api ─────────────────────────────────────────

@app.get("/api", tags=["Documentation"])
async def swagger_ui():
    """Interactive API documentation (Swagger UI)."""
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="PDF Studio API Docs",
        swagger_favicon_url="/static/favicon.ico",
    )


@app.get("/api/redoc", tags=["Documentation"])
async def redoc_ui():
    """Alternative API documentation (ReDoc)."""
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="PDF Studio API Docs - ReDoc",
    )


@app.get("/", include_in_schema=False)
async def index():
    """Redirect to the web app."""
    return RedirectResponse(url="/static/index.html")


# ── Tool & Category endpoints ────────────────────────────────────────

@app.get(
    "/api/tools",
    response_model=ToolsResponse,
    tags=["Tools"],
    summary="List all available tools",
    description="Returns all 43 PDF tools with schemas and parameter definitions.",
    responses={200: {"description": "Tool list with categories"}},
)
async def tool_schema():
    """Get all available tools and their parameter schemas.

    Returns categories (files, pages, edit, convert, scan, security, misc)
    and the full tool list with parameter definitions for UI generation.
    """
    return {"categories": pdf_tools.CATEGORIES, "tools": pdf_tools.schema()}


@app.get(
    "/api/categories",
    tags=["Tools"],
    summary="List tool categories",
    description="Returns the 7 tool categories.",
)
async def categories():
    """Get tool categories."""
    return {"categories": pdf_tools.CATEGORIES}


# ── Run a tool ───────────────────────────────────────────────────────

@app.post(
    "/api/tools/{tool_id}",
    response_model=JobCreated,
    tags=["Tools"],
    summary="Run a PDF tool",
    description=(
        "Upload files and run a tool. Returns a job_id to poll for results.\n\n"
        "Request body is multipart/form-data with:\n"
        "- **files**: One or more uploaded files\n"
        "- **options**: JSON string with tool-specific parameters\n"
        "- **overlay** (editor only): JSON overlay file"
    ),
    responses={
        200: {"model": JobCreated, "description": "Job submitted"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        404: {"model": ErrorResponse, "description": "Unknown tool"},
    },
)
async def run_tool(
    tool_id: str = Path(..., description="Tool identifier (e.g. merge, rotate, protect)", example="merge"),
    request: Request = ...,
):
    """Submit a PDF processing job.

    Upload files and provide tool-specific options as a JSON string.
    The job runs asynchronously. Poll GET /api/jobs/{job_id} for status.
    """
    tool = pdf_tools.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_id}")

    form = await request.form()
    files = form.getlist("files")
    overlay = form.getlist("overlay")
    opt_field = form.get("options")
    if isinstance(opt_field, UploadFile):
        options_raw = (await opt_field.read()).decode("utf-8", errors="replace")
    else:
        options_raw = opt_field or "{}"
    try:
        options = json.loads(options_raw) if isinstance(options_raw, str) else dict(options_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid options JSON")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    allowed = ALLOWED.get(tool["accept"], {".pdf"})
    if tool["accept"] == "pdf,image":
        allowed = ALLOWED["pdf"] | ALLOWED["image"]
    paths = []
    job_id = str(uuid.uuid4())[:12]
    for f in files:
        if isinstance(f, str):
            continue
        name = f.filename or "upload"
        ext = os.path.splitext(name)[1].lower()
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {name}")
        data = await f.read()
        storage.upload_dir(job_id)
        path = storage.save_upload(job_id, name, data)
        paths.append(path)

    if overlay:
        data = await overlay[0].read()
        paths.append(storage.save_upload(job_id, "overlay.json", data))

    job = jobs.submit(tool_id, tool["handler"], paths, options)
    return JSONResponse({"job_id": job.id})


# ── Job status ───────────────────────────────────────────────────────

@app.get(
    "/api/jobs/{job_id}",
    response_model=JobStatus,
    tags=["Jobs"],
    summary="Get job status",
    description="Poll this endpoint to track job progress.",
    responses={
        200: {"model": JobStatus, "description": "Job status"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def job_status(
    job_id: str = Path(..., description="Job ID from POST /api/tools/{tool_id}", example="abc123def456"),
):
    """Get the current status and progress of a processing job.

    Status values: queued, running, done, error.
    When done, download results via GET /api/download/{job_id}.
    """
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs.to_dict(job)


# ── Download ─────────────────────────────────────────────────────────

@app.get(
    "/api/download/{job_id}",
    tags=["Jobs"],
    summary="Download result file",
    description="Download the output file from a completed job.",
    responses={
        200: {"content": {"application/pdf": {}, "application/zip": {}}},
        400: {"model": ErrorResponse, "description": "Job not finished"},
        404: {"model": ErrorResponse, "description": "Not found"},
    },
)
async def download(
    job_id: str = Path(..., description="Job ID", example="abc123def456"),
    file: str = Query("", description="Specific filename for multi-result jobs"),
):
    """Download the result file from a completed job.

    For single-output tools, omit the file parameter.
    For multi-output tools, the result is a ZIP archive.
    """
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not finished")
    results = job.results
    if file:
        matches = [r for r in results if r["name"] == file]
        if not matches:
            raise HTTPException(status_code=404, detail="File not found")
        r = matches[0]
    else:
        r = results[0]
    if not os.path.exists(r["path"]):
        raise HTTPException(status_code=404, detail="File no longer available")
    return FileResponse(r["path"], filename=r["name"])


# ── Delete job ───────────────────────────────────────────────────────

@app.delete(
    "/api/jobs/{job_id}",
    tags=["Jobs"],
    summary="Delete a job",
    description="Clean up a job and remove all its files.",
    responses={200: {"description": "Job deleted"}},
)
async def delete_job(
    job_id: str = Path(..., description="Job ID to delete"),
):
    """Delete a job and clean up all its files."""
    storage.cleanup_job(job_id)
    return JSONResponse({"ok": True})


# ── Editor endpoints ─────────────────────────────────────────────────

@app.post(
    "/api/editor/render",
    tags=["Editor"],
    summary="Render PDF pages to preview images",
    description="Upload a PDF and render each page as a PNG thumbnail for the canvas editor.",
    responses={200: {"model": JobCreated}},
)
async def editor_render(
    file: UploadFile = File(..., description="PDF file to render"),
    dpi: int = Form(100, description="Render resolution 72-300"),
):
    """Render PDF pages as PNG previews for the editor canvas."""
    job_id = str(uuid.uuid4())[:12]
    data = await file.read()
    storage.upload_dir(job_id)
    path = storage.save_upload(job_id, file.filename or "input.pdf", data)
    job = jobs.submit("editor_render", pdf_tools.edit.render_preview, [path],
                      {"dpi": dpi}, cleanup_inputs=False, zip_outputs=False)
    return JSONResponse({"job_id": job.id})


@app.get(
    "/api/preview/{job_id}",
    tags=["Editor"],
    summary="Get preview render status",
    description="Check if preview thumbnails are ready.",
    responses={
        200: {"model": JobStatus},
        404: {"model": ErrorResponse, "description": "Preview not ready"},
    },
)
async def preview(
    job_id: str = Path(..., description="Preview job ID"),
):
    """Get the status of a preview render job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=404, detail="Preview not ready")
    return jobs.to_dict(job)


@app.post(
    "/api/preview/result/{job_id}",
    tags=["Editor"],
    summary="Render result as preview thumbnails",
    description="Render a completed job PDF output as thumbnails.",
    responses={
        200: {"model": JobCreated},
        400: {"model": ErrorResponse},
    },
)
async def preview_result(
    job_id: str = Path(..., description="Completed tool job ID"),
    dpi: int = Form(100, description="Render resolution 72-300"),
):
    """Render a completed job's PDF output as page thumbnails."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not finished")
    result = job.results[0] if job.results else None
    if not result or not os.path.splitext(result["name"])[1].lower() == ".pdf":
        raise HTTPException(status_code=400, detail="Result is not a PDF")
    if not os.path.exists(result["path"]):
        raise HTTPException(status_code=404, detail="File no longer available")
    pjob = jobs.submit("result_render", pdf_tools.edit.render_preview, [result["path"]],
                       {"dpi": dpi}, cleanup_inputs=False, zip_outputs=False)
    return JSONResponse({"job_id": pjob.id})


# ── Static files (must be last) ─────────────────────────────────────

app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ── Entry point ──────────────────────────────────────────────────────

# Start the FastAPI server with Uvicorn.
def main():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
