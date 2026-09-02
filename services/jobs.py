"""Thread-pool job runner with progress tracking and result registry."""
import asyncio
import os
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

import services.storage as storage

executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pdf")
_lock = threading.Lock()
_JOBS: dict[str, "Job"] = {}
_counter = 0


class JobError(Exception):
    pass


@dataclass
class Job:
    id: str
    tool: str
    status: str = "queued"           # queued | running | done | error
    progress: int = 0
    message: str = ""
    error: str = ""
    results: list[dict] = field(default_factory=list)  # [{name, path}]
    created: float = field(default_factory=time.time)

    # Update job progress, message, and/or status.
    def update(self, progress: int = None, message: str = None, status: str = None):
        with _lock:
            if progress is not None:
                self.progress = progress
            if message is not None:
                self.message = message
            if status is not None:
                self.status = status


# Generate a unique job ID using timestamp and counter.
def _new_id() -> str:
    global _counter
    _lock.acquire()
    try:
        _counter += 1
        return f"{int(time.time())}-{_counter}"
    finally:
        _lock.release()


# Submit a new job to the thread pool for async execution.
def submit(tool: str, handler: Callable, input_paths: list[str], options: dict,
           cleanup_inputs: bool = True, zip_outputs: bool = True) -> Job:
    job_id = _new_id()
    job = Job(id=job_id, tool=tool)
    with _lock:
        _JOBS[job_id] = job

    # Background worker: execute handler, process outputs, update job status.
    def run():
        job.update(status="running", progress=2, message="Starting…")
        try:
            outputs = handler(input_paths, options, job)
            # outputs: list of (display_name, abs_path)
            result_dir = storage.result_dir(job_id)
            zipped = False
            if len(outputs) == 1:
                name, path = outputs[0]
                final = os.path.join(result_dir, name)
                _move(path, final)
                job.results = [{"name": name, "path": final}]
            elif len(outputs) > 1 and zip_outputs:
                zipped = True
                zip_path = os.path.join(result_dir, f"{tool}.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for name, path in outputs:
                        zf.write(path, os.path.basename(name))
                job.results = [{"name": f"{tool}.zip", "path": zip_path}]
            elif len(outputs) > 1:
                results = []
                for name, path in outputs:
                    final = os.path.join(result_dir, os.path.basename(name))
                    _move(path, final)
                    results.append({"name": os.path.basename(name), "path": final})
                job.results = results
            else:
                raise JobError("Tool produced no output files.")
            job.update(progress=100, status="done", message="Done")
            _cleanup_inputs(input_paths, cleanup_inputs)
        except Exception as e:  # noqa: BLE001
            job.error = str(e)
            job.update(status="error", message="Failed")
            _cleanup_inputs(input_paths, cleanup_inputs)

    executor.submit(run)
    return job


# Move a file from src to dst using shutil.
def _move(src, dst):
    import shutil
    shutil.move(src, dst)


# Remove input files if cleanup is enabled.
def _cleanup_inputs(paths, enabled):
    if not enabled:
        return
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass


# Retrieve a job by its ID.
def get(job_id: str) -> Optional[Job]:
    with _lock:
        return _JOBS.get(job_id)


# Convert a Job object to a dictionary for API responses.
def to_dict(job: Job) -> dict:
    base = os.path.dirname(job.results[0]["path"]) if job.results else ""
    return {
        "id": job.id,
        "tool": job.tool,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "results": [
            {"name": r["name"], "url": f"/api/download/{job.id}?file={r['name']}"}
            for r in job.results
        ],
        "zipped": bool(len(job.results) > 1 or (job.results and job.results[0]["name"].endswith(".zip"))),
    }


