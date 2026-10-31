"""Aurora/Postgres chunk repository implementing the ChunkRepository port.

Chunks are keyed by a deterministic ``chunk_id`` so a reprocess can upsert only
the chunks that actually changed. Removed chunks are marked inactive instead of
being deleted immediately, which keeps citations from older answers readable
during their retention window. Every statement carries ``company_id`` so the
partitioned table is pruned to one tenant partition and RLS applies as a second
lock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.chunk_repository import ChunkRepository as ChunkRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.domain.entities.chunk import Chunk


class PostgresChunkRepository(ChunkRepositoryPort, BaseRepository):
    """Chunk repository with stable-id upserts and tenant-scoped lifecycle flags.

    When constructed without a session the adapter keeps state in memory. That
    mode exists for contract tests and the pilot composition path where no
    database is wired; it is never used while a session is present.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, Chunk]] = {}

    async def upsert_chunk(self, company_id: Any, *args: Any, **kwargs: Any) -> Chunk:
        from ._postgres_chunk_repository_upsert_chunk import _upsert_chunk as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def upsert_chunks(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Chunk]:
        from ._postgres_chunk_repository_upsert_chunks import _upsert_chunks as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def get_chunk(self, company_id: Any, *args: Any, **kwargs: Any) -> Chunk | None:
        from ._postgres_chunk_repository_get_chunk import _get_chunk as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def list_chunks_by_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[Chunk]:
        from ._postgres_chunk_repository_list_chunks_by_version import (
            _list_chunks_by_version as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def list_chunks_by_document(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[Chunk]:
        from ._postgres_chunk_repository_list_chunks_by_document import (
            _list_chunks_by_document as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def mark_chunks_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_chunk_repository_mark_chunks_inactive import (
            _mark_chunks_inactive as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def mark_version_chunks_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_chunk_repository_mark_version_chunks_inactive import (
            _mark_version_chunks_inactive as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def delete_chunks_by_version(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_chunk_repository_delete_chunks_by_version import (
            _delete_chunks_by_version as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    # ------------------------------------------------------------------
    # In-memory backend (no session wired).
    # ------------------------------------------------------------------

    def _upsert_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Chunk]:
        from ._postgres_chunk_repository__upsert_memory import _upsert_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

    def _mark_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_chunk_repository__mark_memory import _mark_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

    def _delete_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_chunk_repository__delete_memory import _delete_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)


# Naming variants used across the project/tests.

# Compatibility aliases (preserved for external imports)
AuroraChunkRepository = PostgresChunkRepository
ChunkRepo = PostgresChunkRepository
ChunkRepositoryAdapter = PostgresChunkRepository
PostgresChunkRepo = PostgresChunkRepository
RLSChunkRepository = PostgresChunkRepository
