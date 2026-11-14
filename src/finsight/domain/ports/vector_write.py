"""Port for writing chunk vectors independently of vector search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import ChunkId, CompanyId
    from finsight.domain.entities.chunk import Chunk


class VectorWrite(ABC):
    """Interface for version-safe vector writes.

    A reprocess writes the new version's vectors as inactive and commits them in
    one step, so a search can never see old and new vectors from the same
    document at the same time.
    """

    @abstractmethod
    async def upsert_chunks(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        chunks: Sequence[Chunk],
        vectors: object,
        only_changed: bool = True,
        **kwargs: object,
    ) -> int:
        """Write vectors for new or changed chunks and return how many were written."""
        _ = (version_id, chunks, vectors, only_changed, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def mark_version_inactive(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[ChunkId] = (),
        **kwargs: object,
    ) -> int:
        """Hide a version's vectors without deleting them."""
        _ = (version_id, exclude_chunk_ids, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def commit_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        """Atomically make one version the only active vector set for its chunks."""
        _ = (version_id, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def delete_chunks(
        self,
        company_id: CompanyId,
        chunk_ids: Sequence[ChunkId],
        **kwargs: object,
    ) -> int:
        """Permanently remove the given vectors and return the count."""
        _ = (chunk_ids, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def delete_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        """Permanently remove a version's vectors and return the count."""
        _ = (version_id, kwargs)
        raise NotImplementedError


__all__ = ['VectorWrite']
