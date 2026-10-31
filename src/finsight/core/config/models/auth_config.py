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


class AuthConfig(StrictBaseModel):
    user_pool_id: str
    client_id: str
    region: str
    jwks_cache_ttl_seconds: int = Field(ge=1)
    token_verification_clock_skew_seconds: int = Field(ge=0)
