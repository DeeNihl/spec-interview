"""Typed application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["mock", "gemma-local", "parlor-gemma", "nova-sonic"]


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: Path = Field(
        default_factory=lambda: Path(
            os.getenv("SPEC_INTERVIEW_DATA_DIR", ".spec-interview/sessions")
        )
    )
    parlor_endpoint: str = Field(
        default_factory=lambda: os.getenv("SPEC_INTERVIEW_PARLOR_ENDPOINT", "http://127.0.0.1:8765")
    )
    gemma_endpoint: str = Field(
        default_factory=lambda: os.getenv("SPEC_INTERVIEW_GEMMA_ENDPOINT", "http://127.0.0.1:8081")
    )
    gemma_model: str = Field(
        default_factory=lambda: os.getenv("SPEC_INTERVIEW_GEMMA_MODEL", "gemma4-e4b")
    )
    gemma_api_key: str | None = Field(
        default_factory=lambda: os.getenv("SPEC_INTERVIEW_GEMMA_API_KEY")
    )
    aws_region: str | None = Field(
        default_factory=lambda: os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    )
