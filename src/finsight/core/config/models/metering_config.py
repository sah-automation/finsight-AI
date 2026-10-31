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


class MeteringConfig(StrictBaseModel):
    table_name: str
    flush_interval_seconds: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    price_table: str = 'config/prices.yaml'
    shared_cost_split: str = 'requests_and_runtime'
    reconcile_tolerance_percent: int = Field(ge=1, le=25, default=10)
