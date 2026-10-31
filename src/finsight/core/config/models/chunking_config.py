from pydantic import Field

from .chunking_strategy import ChunkingStrategy
from .strict_base_model import (
    StrictBaseModel,
)


class ChunkingConfig(StrictBaseModel):
    strategy: ChunkingStrategy
    max_chunk_tokens: int = Field(ge=1)
    overlap_tokens: int = Field(ge=0)
    min_chunk_tokens: int = Field(ge=1)
    respect_boundaries: bool
