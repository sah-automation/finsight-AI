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


class AccessConfig(StrictBaseModel):
    roles: list[str] = Field(
        default_factory=lambda: [
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        ]
    )
    permissions_file: str = 'config/permissions.yaml'
    role_cache_seconds_privileged: int = Field(ge=0, default=0)
    users_per_company_max: int = Field(ge=1, default=10)
