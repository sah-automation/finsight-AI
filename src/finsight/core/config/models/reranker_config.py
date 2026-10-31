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


class RerankerConfig(StrictBaseModel):
    provider: str
    model: str
    top_n: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    batch_size: int = Field(ge=1)
