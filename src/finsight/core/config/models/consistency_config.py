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


class ConsistencyConfig(StrictBaseModel):
    check_interval_seconds: int = Field(ge=1, default=300)
    fresh_read_window_seconds: int = Field(ge=0, le=60, default=10)
    job_max_receive_count: int = Field(ge=1, le=10, default=5)
