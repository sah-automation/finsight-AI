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


class RetrievalConfig(StrictBaseModel):
    hybrid_search_enabled: bool = True
    vector_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    keyword_weight: float = Field(ge=0.0, le=1.0, default=0.3)
    top_k: int = Field(ge=1, default=50)
    rerank_top_n: int = Field(ge=1, default=20)
    rerank_parallel_batches: int = Field(ge=1, default=2)
    evidence_min_score: float = Field(ge=0.0, le=1.0, default=0.30)
    evidence_min_search_score: float = Field(ge=0.0, le=1.0, default=0.50)
    evidence_min_chunks: int = Field(ge=1, default=1)

    @model_validator(mode='after')
    def validate_scores(self) -> RetrievalConfig:
        if self.evidence_min_search_score < self.evidence_min_score:
            raise ValueError('evidence_min_search_score must be >= evidence_min_score')
        return self
