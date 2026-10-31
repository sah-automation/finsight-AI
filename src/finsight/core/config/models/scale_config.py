from typing import Literal

from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel

_REGISTERED_VECTOR_STORES = {'aurora_pgvector'}


class ScaleConfig(StrictBaseModel):
    cells: int = Field(ge=1, default=1)
    vector_store: str = 'aurora_pgvector'
    ingestion_max_parallel_jobs_per_company: int = Field(ge=1, default=1)
    reprocess_max_parallel_companies: int = Field(ge=1, default=1)
    queue_priority: Literal['quick_first', 'first_come'] = 'quick_first'
    queue_max_wait_seconds: int = Field(ge=1, le=30, default=5)

    @model_validator(mode='after')
    def validate_vector_store(self) -> 'ScaleConfig':
        if self.vector_store not in _REGISTERED_VECTOR_STORES:
            raise ValueError(f'unknown vector store: {self.vector_store}')
        return self
