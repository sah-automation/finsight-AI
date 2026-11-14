"""Auto-extracted helper for PostgresChunkRepository.upsert_chunk."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.chunk import Chunk

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _upsert_chunk(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    chunk: Chunk,
    **kwargs: object,
) -> Chunk:
    saved = await self.upsert_chunks(company_id, [chunk], **kwargs)
    return saved[0] if saved else chunk
