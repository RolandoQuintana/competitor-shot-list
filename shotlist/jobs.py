"""In-process analyze job registry and execution."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from shotlist.config import Settings, get_settings
from shotlist.errors import InvalidVideoUrlError, PipelineError
from shotlist.pipeline import analyze_fixture, analyze_youtube_url


@dataclass(frozen=True)
class AnalyzeJobRequest:
    url: str | None
    fixture: bool
    settings: Settings | None = None


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobError:
    code: str
    message: str
    http_status: int = 500

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}

    @classmethod
    def from_exception(cls, exc: BaseException) -> JobError:
        if isinstance(exc, PipelineError):
            return cls(exc.api_code, str(exc), exc.http_status)
        return cls("internal_error", str(exc), 500)


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output_dir: Path | None = None
    video_id: str | None = None
    error: JobError | None = None

    def to_dict(self, settings: Settings | None = None) -> dict[str, Any]:
        settings = settings or get_settings()
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }
        if self.started_at is not None:
            payload["started_at"] = self.started_at.isoformat()
        if self.finished_at is not None:
            payload["finished_at"] = self.finished_at.isoformat()
        if self.video_id is not None:
            payload["video_id"] = self.video_id
        if self.output_dir is not None:
            payload["output_dir"] = _public_output_path(self.output_dir, settings)
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload


def _public_output_path(path: Path, settings: Settings) -> str:
    """Prefer a stable path relative to OUTPUT_DIR when possible."""
    try:
        return str(path.resolve().relative_to(settings.output_dir.resolve()))
    except ValueError:
        return str(path)


def run_analyze_job(
    *,
    url: str | None,
    fixture: bool,
    settings: Settings | None = None,
) -> Path:
    """Same orchestration as ``shotlist analyze`` (sync, for worker thread)."""
    settings = settings or get_settings()
    if fixture:
        return analyze_fixture(settings)
    if not url:
        raise InvalidVideoUrlError("provide url or fixture=true")
    return analyze_youtube_url(url, settings)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def _enqueue_job(self) -> JobRecord:
        job_id = uuid.uuid4().hex
        record = JobRecord(job_id=job_id, status=JobStatus.QUEUED)
        async with self._lock:
            self._jobs[job_id] = record
        return record

    async def create(self, request: AnalyzeJobRequest) -> JobRecord:
        record = await self._enqueue_job()
        asyncio.create_task(self._run(record.job_id, request))
        return record

    async def run_sync(self, request: AnalyzeJobRequest) -> JobRecord:
        record = await self._enqueue_job()
        await self._run(record.job_id, request)
        return record

    async def _run(self, job_id: str, request: AnalyzeJobRequest) -> None:
        record = self._jobs[job_id]
        record.status = JobStatus.RUNNING
        record.started_at = datetime.now(timezone.utc)
        settings = request.settings or get_settings()
        try:
            out_dir = await asyncio.to_thread(
                run_analyze_job,
                url=request.url,
                fixture=request.fixture,
                settings=settings,
            )
            record.output_dir = out_dir
            record.video_id = out_dir.name
            record.status = JobStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001
            record.error = JobError.from_exception(exc)
            record.status = JobStatus.FAILED
        finally:
            record.finished_at = datetime.now(timezone.utc)


job_store = JobStore()
