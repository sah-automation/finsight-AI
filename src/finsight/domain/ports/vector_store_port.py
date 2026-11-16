"""Unified port for vector store operations (read + write)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import CompanyId
    from finsight.domain.entities.chunk import Chunk


class VectorStorePort(ABC):
    """Unified interface for vector store read and write operations.

    Combines VectorWrite and VectorSearch into a single port for
    implementations that provide both capabilities.
    """

    # --- Write operations (from VectorWrite) ---

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
        raise NotImplementedError

    @abstractmethod
    async def mark_version_inactive(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[Any] = (),
        **kwargs: object,
    ) -> int:
        """Hide a version's vectors without deleting them."""
        raise NotImplementedError

    @abstractmethod
    async def commit_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        """Atomically make one version the only active vector set for its chunks."""
        raise NotImplementedError

    @abstractmethod
    async def delete_chunks(
        self,
        company_id: CompanyId,
        chunk_ids: Sequence[Any],
        **kwargs: object,
    ) -> int:
        """Permanently remove the given vectors and return the count."""
        raise NotImplementedError

    @abstractmethod
    async def delete_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        """Permanently remove a version's vectors and return the count."""
        raise NotImplementedError

    # --- Read operations (from VectorSearch/HybridSearch) ---

    @abstractmethod
    async def search(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        """Search candidates for a company."""
        raise NotImplementedError


# Compatibility aliases
VectorWritePort = VectorStorePort
VectorSearchPort = VectorStorePort

__all__ = ['VectorSearchPort', 'VectorStorePort', 'VectorWritePort']
