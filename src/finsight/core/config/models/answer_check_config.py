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


class AnswerCheckConfig(StrictBaseModel):
    enabled: bool = True
    retry_max: int = Field(ge=0, le=1, default=1)
    retry_time_limit_seconds: int = Field(ge=1, le=4, default=4)
