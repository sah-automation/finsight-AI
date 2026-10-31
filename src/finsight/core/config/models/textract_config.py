from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class TextractConfig(StrictBaseModel):
    async_enabled: bool
    poll_interval_seconds: int = Field(ge=1)
    max_poll_attempts: int = Field(ge=1)
    feature_types: list[str]
    region: str
