"""
FastAPI application for AI Doc Generator.

Provides a REST API endpoint to trigger documentation generation
for a given repository URL or local path.
"""

import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator

from logger import setup_logger
from config import settings

logger = setup_logger("api")

app = FastAPI(
    title="AI Doc Generator API",
    description="Automatically generate documentation for any software repository.",
    version="0.1.0",
)


# Only allow HTTPS URLs from trusted Git hosting providers.
_ALLOWED_REMOTE_URL = re.compile(
    r"^https://(github|gitlab)\.com/[\w\-\.]{1,100}/[\w\-\.]{1,100}(\.git)?/?$"
)


class GenerateRequest(BaseModel):
    """Request schema for documentation generation."""

    source: str
    output_dir: str | None = None

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v: object) -> str:
        """Block path traversal and restrict remote URLs to GitHub/GitLab HTTPS."""
        if not isinstance(v, str):
            raise ValueError("source must be a string")
        v = v.strip()
        if not v:
            raise ValueError("source must not be empty")

        is_remote = v.startswith(("https://", "http://", "git@", "ssh://"))
        if is_remote:
            if not _ALLOWED_REMOTE_URL.match(v):
                raise ValueError(
                    "Only GitHub and GitLab HTTPS URLs are accepted. "
                    "Example: https://github.com/owner/repo"
                )
        else:
            # Local path — resolve and check for path traversal
            try:
                resolved = Path(v).expanduser().resolve()
            except Exception as exc:
                raise ValueError(f"Invalid path: {exc}") from exc
            # Reject paths that try to escape into sensitive system directories
            forbidden_prefixes = ("/etc", "/proc", "/sys", "/root", "/boot")
            if any(str(resolved).startswith(p) for p in forbidden_prefixes):
                raise ValueError("Access to system paths is not allowed")
        return v

    @field_validator("output_dir", mode="before")
    @classmethod
    def validate_output_dir(cls, v: object) -> str | None:
        """Prevent output_dir path traversal."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("output_dir must be a string")
        v = v.strip()
        try:
            resolved = Path(v).expanduser().resolve()
        except Exception as exc:
            raise ValueError(f"Invalid output_dir: {exc}") from exc
        forbidden_prefixes = ("/etc", "/proc", "/sys", "/root", "/boot")
        if any(str(resolved).startswith(p) for p in forbidden_prefixes):
            raise ValueError("Access to system paths is not allowed for output_dir")
        return v


class GenerateResponse(BaseModel):
    """Response schema for documentation generation."""

    job_id: str
    status: str
    message: str
    output_dir: str | None = None


# In-memory job tracker (replace with Redis in production)
_jobs: dict[str, dict] = {}


def _run_pipeline(job_id: str, source: str, output_dir: str) -> None:
    """Background task that runs the full documentation pipeline."""
    from cli.generate_docs import run_pipeline

    _jobs[job_id]["status"] = "running"
    try:
        run_pipeline(source=source, output_dir=output_dir)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["output_dir"] = output_dir
    except Exception as exc:
        logger.error("Pipeline failed for job %s: %s", job_id, exc)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)


@app.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate_docs(
    request: GenerateRequest, background_tasks: BackgroundTasks
) -> GenerateResponse:
    """
    Trigger async documentation generation.

    Args:
        request: Contains the source (URL or local path) and optional output dir.
        background_tasks: FastAPI background task runner.

    Returns:
        Job ID and initial status.
    """
    job_id = str(uuid.uuid4())
    output_dir = request.output_dir or settings.output_dir

    _jobs[job_id] = {"status": "queued", "output_dir": output_dir}
    background_tasks.add_task(_run_pipeline, job_id, request.source, output_dir)

    logger.info("Queued job %s for source: %s", job_id, request.source)
    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message="Documentation generation started.",
        output_dir=output_dir,
    )


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """
    Get the status of a documentation generation job.

    Args:
        job_id: UUID of the job.

    Returns:
        Job status dict.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, **_jobs[job_id]}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
