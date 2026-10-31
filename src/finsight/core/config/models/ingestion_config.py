from typing import Literal

from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel

_REQUIRED_METADATA = {'company', 'period', 'category', 'currency', 'units', 'page'}


class IngestionConfig(StrictBaseModel):
    max_document_size_mb: int = Field(ge=1, default=100)
    allowed_mime_types: list[str] = Field(default_factory=list)
    virus_scan_enabled: bool = True
    page_router_enabled: bool = True
    chunk_strategy: Literal['structure_recursive', 'plain_recursive'] = 'structure_recursive'
    child_chunk_tokens: int = Field(ge=200, le=800, default=500)
    parent_mode: Literal['section', 'page'] = 'section'
    max_parent_tokens: int = Field(ge=1, default=1500)
    llm_context_categories: list[str] = Field(default_factory=list)
    required_metadata: list[str] = Field(
        default_factory=lambda: [
            'company',
            'period',
            'category',
            'currency',
            'units',
            'page',
            'table_id',
        ]
    )

    @model_validator(mode='after')
    def _validate_ingestion_rules(self) -> 'IngestionConfig':
        if self.max_parent_tokens < self.child_chunk_tokens:
            raise ValueError('max_parent_tokens must be at least child_chunk_tokens')
        if not _REQUIRED_METADATA.issubset(set(self.required_metadata)):
            missing = sorted(_REQUIRED_METADATA - set(self.required_metadata))
            raise ValueError('required_metadata must include ' + ', '.join(missing))
        return self
