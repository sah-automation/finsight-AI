from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .pii_action import PiiAction
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class SecurityConfig(StrictBaseModel):
    require_company_id_on_all_queries: bool
    pii_detection_enabled: bool
    pii_action: PiiAction
    prompt_injection_detection_enabled: bool
    max_question_length: int = Field(ge=1)
    max_context_tokens: int = Field(ge=1)


# Additional Phase 1 sections (minimal required)
