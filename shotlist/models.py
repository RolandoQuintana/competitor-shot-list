"""Pydantic models for shot-list.json schema v1.0."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ShotType(StrEnum):
    TALKING_HEAD = "talking_head"
    POV = "pov"
    B_ROLL = "b_roll"
    SCREEN_RECORDING = "screen_recording"
    PRODUCT_CLOSEUP = "product_closeup"
    TEXT_CARD = "text_card"
    MONTAGE = "montage"
    OTHER = "other"


class Framing(StrEnum):
    CLOSE = "close"
    MEDIUM = "medium"
    WIDE = "wide"
    OTHER = "other"


class CameraMovement(StrEnum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    ZOOM = "zoom"
    HANDHELD = "handheld"
    TRACKING = "tracking"
    OTHER = "other"


class Role(StrEnum):
    HOOK = "hook"
    SETUP = "setup"
    PROOF = "proof"
    TRANSITION = "transition"
    CTA = "cta"
    PUNCHLINE = "punchline"
    OTHER = "other"


SCHEMA_VERSION = "1.0"


class VideoMetadata(BaseModel):
    url: str
    video_id: str
    title: str
    channel: str
    duration_sec: float = Field(gt=0)
    thumbnail_url: str | None = None
    analyzed_at: datetime


class Analysis(BaseModel):
    vision_error_count: int = 0
    pipeline_version: str | None = None
    models: dict[str, Any] | None = None


class TranscriptSegment(BaseModel):
    start_sec: float = Field(ge=0)
    end_sec: float
    text: str

    @model_validator(mode="after")
    def end_after_start(self) -> TranscriptSegment:
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class Transcript(BaseModel):
    full_text: str
    segments: list[TranscriptSegment] | None = None


class Shot(BaseModel):
    index: int = Field(ge=1)
    start_sec: float = Field(ge=0)
    end_sec: float
    time_label: str
    shot_type: ShotType
    visual: str
    dialogue: str
    on_screen_text: str | None = ""
    framing: Framing | None = None
    camera_movement: CameraMovement | None = None
    role: Role | None = None
    notes: str | None = None

    @field_validator("on_screen_text", mode="before")
    @classmethod
    def normalize_on_screen_text(cls, v: str | None) -> str:
        if v is None:
            return ""
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> Shot:
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class ShotList(BaseModel):
    schema_version: str = SCHEMA_VERSION
    video: VideoMetadata
    analysis: Analysis = Field(default_factory=Analysis)
    transcript: Transcript
    shots: list[Shot]

    @field_validator("schema_version")
    @classmethod
    def schema_must_be_v1(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        return v
