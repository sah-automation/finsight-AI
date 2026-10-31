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


class ModelConfig(StrictBaseModel):
    provider: str = 'litellm'
    model_id: str
    max_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    retry_base_delay_seconds: float = Field(ge=0.0, default=1.0)
