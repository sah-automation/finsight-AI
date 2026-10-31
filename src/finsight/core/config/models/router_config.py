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


class RouterConfig(StrictBaseModel):
    num_retries: int = Field(ge=0)
    retry_after: int = Field(ge=1)
    allowed_fails: int = Field(ge=0)
    cooldown_time: int = Field(ge=1)
