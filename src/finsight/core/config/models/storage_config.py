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


class StorageConfig(StrictBaseModel):
    documents_bucket: str
    reports_bucket: str
    backups_bucket: str
    region: str
    presigned_url_expiry_seconds: int = Field(ge=1)
    multipart_threshold_mb: int = Field(ge=1)
    multipart_chunksize_mb: int = Field(ge=1)
