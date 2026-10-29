"""Contract tests for the HybridSearch port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.vector_store.aurora_pg_vector_search import AuroraPgVectorSearch
from finsight.core.types import ChunkId, CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk

if TYPE_CHECKING:
    from finsight.domain.ports import HybridSearch

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
DOCUMENT = DocumentId('document-a')
OTHER_DOCUMENT = DocumentId('document-b')


def _chunk(text: str, *, document_id: DocumentId = DOCUMENT, version: str = 'v1') -> Chunk:
    return Chunk.create(
        company_id=COMPANY,
        document_id=document_id,
        version_id=version,
        text=text,
        embedding_model_version='embedding-v1',
    )


async def _seed(search: HybridSearch) -> None:
    revenue = _chunk('Revenue was 100 million in 2025.')
    profit = _chunk('Net profit was 20 million in 2025.', document_id=OTHER_DOCUMENT)
    hidden = _chunk('Secret board notes about revenue.')
    hidden.is_active = False
    other_tenant = Chunk.create(
        company_id=OTHER_COMPANY,
        document_id=DOCUMENT,
        version_id='v1',
        text='Revenue was 900 million in 2025.',
        embedding_model_version='embedding-v1',
    )
    await search.index_chunks(  # type: ignore[attr-defined]
        COMPANY,
        [revenue, profit, hidden],
        vectors=[[1.0, 0.0], [0.8, 0.2], [1.0, 0.0]],
        categories=['financial_statement', 'board_report', 'financial_statement'],
    )
    await search.index_chunks(  # type: ignore[attr-defined]
        OTHER_COMPANY,
        [other_tenant],
        vectors=[[1.0, 0.0]],
        categories=['financial_statement'],
    )


@pytest.fixture
def search() -> HybridSearch:
    return AuroraPgVectorSearch()


class TestHybridSearchContract:
    async def test_company_isolation_and_active_chunks(self, search: HybridSearch) -> None:
        await _seed(search)

        results = await search.search(COMPANY, query='revenue', embedding=[1.0, 0.0])

        assert {result.document_id for result in results} == {str(DOCUMENT), str(OTHER_DOCUMENT)}
        assert all(result.company_id == str(COMPANY) for result in results)
        assert all(result.text != 'Secret board notes about revenue.' for result in results)

    async def test_access_scope_filters_categories(self, search: HybridSearch) -> None:
        await _seed(search)

        results = await search.search(
            COMPANY,
            query='profit',
            embedding=[0.8, 0.2],
            access_scope=['financial_statement'],
        )

        assert [result.document_id for result in results] == [str(DOCUMENT)]

    async def test_hybrid_fusion_honours_configured_weights(self, search: HybridSearch) -> None:
        await _seed(search)

        keyword_heavy = await search.search(
            COMPANY,
            query='net profit',
            embedding=[1.0, 0.0],
            vector_weight=0.0,
            keyword_weight=1.0,
        )
        vector_heavy = await search.search(
            COMPANY,
            query='net profit',
            embedding=[1.0, 0.0],
            vector_weight=1.0,
            keyword_weight=0.0,
        )

        assert keyword_heavy[0].document_id == str(OTHER_DOCUMENT)
        assert vector_heavy[0].document_id == str(DOCUMENT)
        assert all(result.vector_score is not None for result in vector_heavy)
        assert all(result.keyword_score is not None for result in keyword_heavy)

    async def test_hybrid_switch_off_uses_vector_only(self) -> None:
        search = AuroraPgVectorSearch(hybrid_search_enabled=False)
        await _seed(search)

        results = await search.search(COMPANY, query='net profit', embedding=[1.0, 0.0])

        assert results[0].document_id == str(DOCUMENT)
        assert results[0].keyword_score == 0.0

    async def test_filters_by_document_and_version(self, search: HybridSearch) -> None:
        await _seed(search)

        by_document = await search.search(
            COMPANY,
            query='million',
            embedding=[0.8, 0.2],
            document_ids=[str(OTHER_DOCUMENT)],
        )
        by_version = await search.search(
            COMPANY,
            query='million',
            embedding=[0.8, 0.2],
            version_ids=['v1'],
        )

        assert [result.document_id for result in by_document] == [str(OTHER_DOCUMENT)]
        assert len(by_version) == 2

    async def test_results_are_typed_and_citable(self, search: HybridSearch) -> None:
        await _seed(search)

        result = (await search.search(COMPANY, query='revenue', embedding=[1.0, 0.0]))[0]

        assert result.chunk_id
        assert result.document_id
        assert result.version_id
        assert result.text
        assert result.score >= 0.0
        assert result['chunk_id'] == result.chunk_id
        assert result.get('document_id') == result.document_id
        assert ChunkId(result.chunk_id)


async def test_search_requires_company_id(search: HybridSearch) -> None:
    with pytest.raises((TypeError, ValueError)):
        await search.search(None, query='revenue')  # type: ignore[arg-type]
