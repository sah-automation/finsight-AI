from __future__ import annotations

from typing import Literal

from pydantic import Field

from .strict_base_model import StrictBaseModel


class ScaleConfig(StrictBaseModel):
    cells: int = Field(ge=1, default=1)
    vector_store: str = 'aurora_pgvector'
    ingestion_max_parallel_jobs_per_company: int = Field(ge=1, default=1)
    reprocess_max_parallel_companies: int = Field(ge=1, default=1)
    queue_priority: Literal['quick_first', 'first_come'] = 'quick_first'
    queue_max_wait_seconds: int = Field(ge=0, default=5)
