"""FastAPI HTTP surface for the analyze pipeline."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field, model_validator

from shotlist.config import get_settings
from shotlist.jobs import AnalyzeJobRequest, JobRecord, JobStatus, job_store
from shotlist.slack_app import (
    get_slack_settings,
    mount_slack_on_fastapi,
    stop_socket_mode,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    handler = getattr(app.state, "slack_socket_handler", None)
    socket_task: asyncio.Task[None] | None = None
    if handler is not None:
        socket_task = asyncio.create_task(handler.start_async())
    try:
        yield
    finally:
        await stop_socket_mode(handler)
        if socket_task is not None:
            socket_task.cancel()
            with asyncio.suppress(asyncio.CancelledError):
                await socket_task


def create_app() -> FastAPI:
    app = FastAPI(
        title="competitor-shot-list",
        description="YouTube Short → shot-list.json + shot-list.md",
        version="0.1.0",
        lifespan=_lifespan,
    )
    slack_settings = get_slack_settings()
    if slack_settings is not None:
        _, socket_handler = mount_slack_on_fastapi(app, slack_settings)
        app.state.slack_socket_handler = socket_handler
    else:
        app.state.slack_socket_handler = None
    return app


app = create_app()


@app.exception_handler(StarletteHTTPException)
async def flatten_pipeline_job_errors(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Return job failure bodies at top level (not wrapped in ``detail``)."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(exc.detail, status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


class AnalyzeRequest(BaseModel):
    url: str | None = Field(
        default=None,
        description="Public YouTube Short URL",
    )
    fixture: bool = Field(
        default=False,
        description="Run bundled CI sample (mock vision, no YouTube)",
    )

    @model_validator(mode="after")
    def url_or_fixture(self) -> AnalyzeRequest:
        if not self.fixture and not self.url:
            raise ValueError("provide url or set fixture=true")
        if self.fixture and self.url:
            raise ValueError("use either url or fixture, not both")
        return self


def _raise_for_failed_job(record: JobRecord) -> None:
    if record.status != JobStatus.FAILED or record.error is None:
        return
    status = record.error.http_status
    raise HTTPException(
        status_code=status,
        detail={
            "job_id": record.job_id,
            "status": record.status.value,
            "error": record.error.to_dict(),
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    settings = get_settings()
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return record.to_dict(settings)


@app.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    wait: Literal["true", "false"] = Query(
        default="false",
        description="If true, block until the job finishes (may exceed proxy timeouts).",
    ),
) -> dict:
    settings = get_settings()
    request = AnalyzeJobRequest(
        url=body.url, fixture=body.fixture, settings=settings
    )
    if wait == "true":
        record = await job_store.run_sync(request)
        _raise_for_failed_job(record)
        return record.to_dict(settings)

    record = await job_store.create(request)
    return JSONResponse(record.to_dict(settings), status_code=202)
