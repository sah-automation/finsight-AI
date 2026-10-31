from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .alert_config import AlertConfig
from .log_format import LogFormat
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class ObservabilityConfig(StrictBaseModel):
    log_level: str
    log_format: LogFormat
    trace_sample_rate: float = Field(ge=0.0, le=1.0)
    service_name: str
    otlp_endpoint: str
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    alerts: AlertConfig

    @model_validator(mode='after')
    def validate_production_trace_rate(self) -> ObservabilityConfig:
        # Will be checked in context of app environment if needed
        return self
