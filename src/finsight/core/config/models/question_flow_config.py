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


class QuestionFlowConfig(StrictBaseModel):
    first_word_timeout_seconds: float = Field(ge=0.1, default=2.0)
    max_wait_seconds: int = Field(ge=1, default=30)
    evidence_threshold: float = Field(ge=0.0, le=1.0, default=0.7)
