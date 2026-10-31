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


class AlertConfig(StrictBaseModel):
    fallback_model_3_used: bool
    reranker_down: bool
    embedding_retries_exceeded: int = Field(ge=1)
    job_in_retry_list: bool
    role_cache_stale_seconds: int = Field(ge=1)
