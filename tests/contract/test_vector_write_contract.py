"""Contract tests for the VectorWrite port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.vector_store.aurora_pg_vector_write import AuroraPgVectorWrite
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk

if TYPE_CHECKING:
    from finsight.domain.ports import VectorWrite

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
DOCUMENT = DocumentId('document-a')
OTHER_DOCUMENT = DocumentId('document-b')


def _chunk(text: str, *, version_id: str, size: int = 4) -> Chunk:
    return Chunk.create(
        company_id=COMPANY,
        document_id=DOCUMENT,
        version_id=version_id,
        text=text,
        embedding_model_version='embedding-v1',
    )


def _vector(value: float, size: int = 4) -> list[float]:
    return [value] * size


@pytest.fixture
def writer() -> VectorWrite:
    return AuroraPgVectorWrite()


class TestVectorWriteContract:
    async def test_writes_only_new_or_changed_chunks(self, writer: VectorWrite) -> None:
        chunk = _chunk('Revenue was 100.', version_id='version-1')

        first = await writer.upsert_chunks(
            COMPANY, 'version-1', chunks=[chunk], vectors=[_vector(0.1)]
        )
        unchanged = await writer.upsert_chunks(
            COMPANY, 'version-1', chunks=[chunk], vectors=[_vector(0.2)]
        )
        changed = _chunk('Revenue was 200.', version_id='version-1')
        changed.chunk_id = chunk.chunk_id
        rewritten = await writer.upsert_chunks(
            COMPANY, 'version-1', chunks=[changed], vectors=[_vector(0.3)]
        )

        assert first == 1
        assert unchanged == 0
        assert rewritten == 1

    async def test_only_changed_false_rewrites_every_vector(self, writer: VectorWrite) -> None:
        chunk = _chunk('Revenue was 100.', version_id='version-1')
        await writer.upsert_chunks(COMPANY, 'version-1', chunks=[chunk], vectors=[_vector(0.1)])

        rewritten = await writer.upsert_chunks(
            COMPANY,
            'version-1',
            chunks=[chunk],
            vectors=[_vector(0.2)],
            only_changed=False,
        )

        assert rewritten == 1

    async def test_new_version_stays_inactive_until_committed(self, writer: VectorWrite) -> None:
        old = _chunk('Revenue was 100.', version_id='version-1')
        await writer.upsert_chunks(COMPANY, 'version-1', chunks=[old], vectors=[_vector(0.1)])
        await writer.commit_version(COMPANY, 'version-1')

        new = _chunk('Revenue was 100.', version_id='version-2')
        written = await writer.upsert_chunks(
            COMPANY, 'version-2', chunks=[new], vectors=[_vector(0.1)]
        )
        state = writer._memory[COMPANY][str(new.chunk_id)]  # type: ignore[attr-defined]

        assert written == 0
        assert state['version_id'] == 'version-2'
        assert state['is_active'] is False

        activated = await writer.commit_version(COMPANY, 'version-2')
        assert activated == 1
        assert writer._memory[COMPANY][str(new.chunk_id)]['is_active'] is True  # type: ignore[attr-defined]

    async def test_commit_version_does_not_mix_old_and_new_vectors(
        self, writer: VectorWrite
    ) -> None:
        old = _chunk('Old revenue.', version_id='version-1')
        new = _chunk('New revenue.', version_id='version-2')
        await writer.upsert_chunks(COMPANY, 'version-1', chunks=[old], vectors=[_vector(0.1)])
        await writer.commit_version(COMPANY, 'version-1')
        await writer.upsert_chunks(COMPANY, 'version-2', chunks=[new], vectors=[_vector(0.2)])

        assert writer._memory[COMPANY][str(old.chunk_id)]['is_active'] is True  # type: ignore[attr-defined]
        assert writer._memory[COMPANY][str(new.chunk_id)]['is_active'] is False  # type: ignore[attr-defined]

        await writer.commit_version(COMPANY, 'version-2')

        for record in writer._memory[COMPANY].values():  # type: ignore[attr-defined]
            assert record['is_active'] is (record['version_id'] == 'version-2')

    async def test_commit_version_leaves_other_documents_active(self, writer: VectorWrite) -> None:
        first = Chunk.create(
            company_id=COMPANY,
            document_id=DOCUMENT,
            version_id='version-1',
            text='Revenue was 100.',
            embedding_model_version='embedding-v1',
        )
        other = Chunk.create(
            company_id=COMPANY,
            document_id=OTHER_DOCUMENT,
            version_id='version-1',
            text='Profit was 20.',
            embedding_model_version='embedding-v1',
        )
        await writer.upsert_chunks(
            COMPANY, 'version-1', chunks=[first, other], vectors=[_vector(0.1), _vector(0.2)]
        )
        await writer.commit_version(COMPANY, 'version-1')

        replacement = Chunk.create(
            company_id=COMPANY,
            document_id=DOCUMENT,
            version_id='version-2',
            text='Revenue was 200.',
            embedding_model_version='embedding-v1',
        )
        await writer.upsert_chunks(
            COMPANY, 'version-2', chunks=[replacement], vectors=[_vector(0.3)]
        )
        await writer.commit_version(COMPANY, 'version-2')

        assert writer._memory[COMPANY][str(first.chunk_id)]['is_active'] is False  # type: ignore[attr-defined]
        assert writer._memory[COMPANY][str(replacement.chunk_id)]['is_active'] is True  # type: ignore[attr-defined]
        assert writer._memory[COMPANY][str(other.chunk_id)]['is_active'] is True  # type: ignore[attr-defined]

    async def test_mark_and_delete_are_tenant_scoped(self, writer: VectorWrite) -> None:
        chunk = _chunk('Revenue was 100.', version_id='version-1')
        await writer.upsert_chunks(COMPANY, 'version-1', chunks=[chunk], vectors=[_vector(0.1)])
        await writer.commit_version(COMPANY, 'version-1')

        hidden = await writer.mark_version_inactive(OTHER_COMPANY, 'version-1')
        deleted = await writer.delete_version(OTHER_COMPANY, 'version-1')

        assert hidden == 0
        assert deleted == 0
        assert await writer.mark_version_inactive(COMPANY, 'version-1') == 1
        assert await writer.delete_chunks(COMPANY, [chunk.chunk_id]) == 1
