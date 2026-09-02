"""Temp storage: job dirs, uploads, results, TTL cleanup."""
import os
import shutil
import time

WORKSPACE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
UPLOADS = os.path.join(WORKSPACE, "uploads")
RESULTS = os.path.join(WORKSPACE, "results")
TTL_SECONDS = 30 * 60  # 30 minutes


# Create uploads and results directories if they don't exist.
def init():
    os.makedirs(UPLOADS, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)


# Create a fresh directory for a job, removing any existing one.
def _fresh_dir(base: str, job_id: str) -> str:
    d = os.path.join(base, job_id)
    if os.path.exists(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


# Ensure a directory exists for a job (create if needed).
def _ensure_dir(base: str, job_id: str) -> str:
    d = os.path.join(base, job_id)
    os.makedirs(d, exist_ok=True)
    return d


# Get or create the upload directory for a job (preserves existing uploads).
def upload_dir(job_id: str) -> str:
    return _ensure_dir(UPLOADS, job_id)


# Create a fresh results directory for a job.
def result_dir(job_id: str) -> str:
    return _fresh_dir(RESULTS, job_id)


# Save uploaded file data to the job's upload directory.
def save_upload(job_id: str, filename: str, data: bytes) -> str:
    d = upload_dir(job_id)
    safe = os.path.basename(filename.replace("\\", "/"))
    path = os.path.join(d, safe)
    with open(path, "wb") as f:
        f.write(data)
    return path


# Remove all upload and result directories for a job.
def cleanup_job(job_id: str):
    for base in (UPLOADS, RESULTS):
        shutil.rmtree(os.path.join(base, job_id), ignore_errors=True)


# Delete job directories older than TTL_SECONDS.
def cleanup_ttl():
    now = time.time()
    for base in (UPLOADS, RESULTS):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            path = os.path.join(base, name)
            try:
                if now - os.path.getmtime(path) > TTL_SECONDS:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass