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


class RoleCacheConfig(StrictBaseModel):
    table_name: str
    ttl_seconds: int = Field(ge=_MIN_ROLE_CACHE_TTL_SECONDS)
    key_prefix: str
    max_entry_size_bytes: int = Field(ge=1)
    refresh_ahead_seconds: int = Field(ge=0)
