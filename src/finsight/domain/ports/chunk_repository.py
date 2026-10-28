"""Port for chunk persistence with stable ids and lifecycle flags."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import ChunkId, CompanyId, DocumentId
    from finsight.domain.entities.chunk import Chunk


class ChunkRepository(ABC):
    """Interface for storing chunks; every method is scoped by ``company_id``."""

    @abstractmethod
    async def upsert_chunk(
        self,
        company_id: CompanyId,
        chunk: Chunk,
        **kwargs: object,
    ) -> Chunk:
        """Insert or replace a chunk by its stable ``chunk_id``."""
        _ = (chunk, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def upsert_chunks(
        self,
        company_id: CompanyId,
        chunks: Sequence[Chunk],
        **kwargs: object,
    ) -> list[Chunk]:
        """Insert or replace a batch of chunks by stable ids, atomically per batch."""
        _ = (chunks, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def get_chunk(
        self,
        company_id: CompanyId,
        chunk_id: ChunkId,
        **kwargs: object,
    ) -> Chunk | None:
        """Fetch one chunk by stable id, or ``None`` when absent."""
        _ = (chunk_id, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def list_chunks_by_version(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        include_inactive: bool = False,
        **kwargs: object,
    ) -> list[Chunk]:
        """List the chunks of one document version."""
        _ = (version_id, include_inactive, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def list_chunks_by_document(
        self,
        company_id: CompanyId,
        document_id: DocumentId,
        *,
        version_id: str | None = None,
        include_inactive: bool = False,
        **kwargs: object,
    ) -> list[Chunk]:
        """List a document's chunks, optionally narrowed to one version."""
        _ = (document_id, version_id, include_inactive, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def mark_chunks_inactive(
        self,
        company_id: CompanyId,
        chunk_ids: Sequence[ChunkId],
        **kwargs: object,
    ) -> int:
        """Mark the given chunks inactive and return how many rows changed."""
        _ = (chunk_ids, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def mark_version_chunks_inactive(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[ChunkId] = (),
        **kwargs: object,
    ) -> int:
        """Mark a whole version inactive, keeping any ids that still match."""
        _ = (version_id, exclude_chunk_ids, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def delete_chunks_by_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        """Permanently remove a version's chunks (purge) and return the count."""
        _ = (version_id, kwargs)
        raise NotImplementedError


__all__ = ['ChunkRepository']
