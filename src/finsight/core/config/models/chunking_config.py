from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .chunking_strategy import ChunkingStrategy
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class ChunkingConfig(StrictBaseModel):
    strategy: ChunkingStrategy
    max_chunk_tokens: int = Field(ge=1)
    overlap_tokens: int = Field(ge=0)
    min_chunk_tokens: int = Field(ge=1)
    respect_boundaries: bool
