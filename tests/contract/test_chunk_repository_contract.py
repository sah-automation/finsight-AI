"""Contract tests for the ChunkRepository port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.repositories.postgres_chunk_repository import PostgresChunkRepository
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk

if TYPE_CHECKING:
    from finsight.domain.ports import ChunkRepository

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
DOCUMENT = DocumentId('document-a')


def _chunk(text: str, *, ordinal: int, version_id: str = 'version-1') -> Chunk:
    return Chunk.create(
        company_id=COMPANY,
        document_id=DOCUMENT,
        version_id=version_id,
        text=text,
        ordinal=ordinal,
        page_number=1,
    )


@pytest.fixture
def repository() -> ChunkRepository:
    return PostgresChunkRepository()


class TestChunkRepositoryContract:
    async def test_upserts_are_keyed_by_stable_chunk_id(self, repository: ChunkRepository) -> None:
        first = _chunk('Revenue was 100.', ordinal=0)
        second = _chunk('Revenue was 100.', ordinal=0, version_id='version-2')

        await repository.upsert_chunks(COMPANY, [first])
        await repository.upsert_chunks(COMPANY, [second])

        stored = await repository.list_chunks_by_document(COMPANY, DOCUMENT, include_inactive=True)
        assert len(stored) == 1
        assert stored[0].chunk_id == first.chunk_id
        assert stored[0].version_id == 'version-2'

    async def test_get_chunk_is_tenant_scoped(self, repository: ChunkRepository) -> None:
        chunk = _chunk('Profit was 20.', ordinal=0)
        await repository.upsert_chunk(COMPANY, chunk)

        assert (await repository.get_chunk(COMPANY, chunk.chunk_id)) is not None
        assert (await repository.get_chunk(OTHER_COMPANY, chunk.chunk_id)) is None

    async def test_upsert_rejects_a_chunk_from_another_tenant(
        self, repository: ChunkRepository
    ) -> None:
        foreign = Chunk.create(
            company_id=OTHER_COMPANY,
            document_id=DOCUMENT,
            version_id='version-1',
            text='Foreign chunk.',
        )

        with pytest.raises(ValueError):
            await repository.upsert_chunk(COMPANY, foreign)

    async def test_lists_active_chunks_by_version_and_document(
        self, repository: ChunkRepository
    ) -> None:
        first = _chunk('First.', ordinal=0)
        second = _chunk('Second.', ordinal=1)
        await repository.upsert_chunks(COMPANY, [first, second])
        await repository.mark_chunks_inactive(COMPANY, [second.chunk_id])

        active = await repository.list_chunks_by_version(COMPANY, 'version-1')
        everything = await repository.list_chunks_by_version(
            COMPANY, 'version-1', include_inactive=True
        )
        by_document = await repository.list_chunks_by_document(COMPANY, DOCUMENT)

        assert [chunk.chunk_id for chunk in active] == [first.chunk_id]
        assert len(everything) == len((first, second))
        assert [chunk.chunk_id for chunk in by_document] == [first.chunk_id]

    async def test_mark_version_inactive_can_keep_matching_chunk_ids(
        self, repository: ChunkRepository
    ) -> None:
        first = _chunk('First.', ordinal=0)
        second = _chunk('Second.', ordinal=1)
        await repository.upsert_chunks(COMPANY, [first, second])

        changed = await repository.mark_version_chunks_inactive(
            COMPANY, 'version-1', exclude_chunk_ids=[first.chunk_id]
        )

        assert changed == 1
        remaining = await repository.list_chunks_by_version(COMPANY, 'version-1')
        assert [chunk.chunk_id for chunk in remaining] == [first.chunk_id]

    async def test_delete_by_version_is_tenant_scoped(self, repository: ChunkRepository) -> None:
        chunk = _chunk('Purge me.', ordinal=0, version_id='version-9')
        await repository.upsert_chunk(COMPANY, chunk)

        assert await repository.delete_chunks_by_version(OTHER_COMPANY, 'version-9') == 0
        assert await repository.delete_chunks_by_version(COMPANY, 'version-9') == 1
        assert await repository.list_chunks_by_version(COMPANY, 'version-9') == []
