from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .answer_cache_config import AnswerCacheConfig
from .role_cache_config import RoleCacheConfig
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class CachesConfig(StrictBaseModel):
    answer_cache: AnswerCacheConfig
    role_cache: RoleCacheConfig
