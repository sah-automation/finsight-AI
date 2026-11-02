from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.ingest_document.save_step import SaveStep


class _FakeDocRepo:
    def __init__(self) -> None:
        self.saved = []
        self.superseded = []

    async def upsert_document_version(self, company_id: Any, version: Any) -> Any:
        self.saved.append(version)
        return version

    async def supersede_previous_versions(
        self, company_id: Any, document_id: Any, keep_version_id: Any
    ) -> None:
        self.superseded.append((company_id, document_id, keep_version_id))


class _FakeChunkRepo:
    def __init__(self) -> None:
        self.saved = []

    async def upsert_chunks(self, company_id: Any, chunks: Any) -> Any:
        self.saved.extend(chunks)
        return chunks


class _FakeVectorWrite:
    def __init__(self) -> None:
        self.saved = []

    async def upsert_vectors(self, company_id: Any, vectors: Any) -> Any:
        self.saved.extend(vectors)
        return vectors


class _FakeMetricRepo:
    def __init__(self) -> None:
        self.saved = []

    async def upsert_metrics(self, company_id: Any, metrics: Any) -> Any:
        self.saved.extend(metrics)
        return metrics


class _FakeTableRepo:
    def __init__(self) -> None:
        self.saved = []

    async def upsert_document_tables(self, company_id: Any, tables: Any) -> Any:
        self.saved.extend(tables)
        return tables


class _FakeAnswerCache:
    def __init__(self) -> None:
        self.cleared = []

    async def clear_company(self, company_id: Any) -> None:
        self.cleared.append(company_id)


class _FakePublisher:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, company_id: Any, event: Any) -> None:
        self.published.append(event)

    async def publish_many(self, company_id: Any, events: Any) -> None:
        self.published.extend(events)


def test_save_step_persists_all_artifacts() -> None:
    doc_repo = _FakeDocRepo()
    chunk_repo = _FakeChunkRepo()
    vector_write = _FakeVectorWrite()
    metric_repo = _FakeMetricRepo()
    table_repo = _FakeTableRepo()
    answer_cache = _FakeAnswerCache()
    publisher = _FakePublisher()

    step = SaveStep(
        document_repository=doc_repo,
        chunk_repository=chunk_repo,
        vector_write=vector_write,
        metric_repository=metric_repo,
        document_table_repository=table_repo,
        answer_cache=answer_cache,
        change_event_publisher=publisher,
        config=None,
    )
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        version=SimpleNamespace(document_id='doc1', state='processing'),
        chunks=['chunk1', 'chunk2'],
        chunk_entities=[SimpleNamespace(chunk_id='c1'), SimpleNamespace(chunk_id='c2')],
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        metrics=[{'name': 'Revenue', 'value': 100}],
        tables=[{'rows': [['a', '1']]}],
        document_tables=[{'rows': [['a', '1']]}],
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert len(doc_repo.superseded) == 1
    assert len(chunk_repo.saved) == 2
    assert len(vector_write.saved) == 2
    assert len(metric_repo.saved) == 1
    assert len(table_repo.saved) == 1
    assert answer_cache.cleared == ['co']
    assert len(publisher.published) >= 1
    assert ctx.status == 'committed'
    assert ctx.committed is True


def test_save_step_idempotent_on_committed_version() -> None:
    doc_repo = _FakeDocRepo()
    step = SaveStep(
        document_repository=doc_repo, chunk_repository=None, vector_write=None, config=None
    )
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        version=SimpleNamespace(document_id='doc1', state='committed'),
        chunks=['chunk1'],
        chunk_entities=[SimpleNamespace(chunk_id='c1')],
        vectors=[[0.1, 0.2]],
        metrics=[{'name': 'Revenue', 'value': 100}],
        document_tables=[{'rows': [['a', '1']]}],
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.committed is True
    assert ctx.idempotent is True
    assert ctx.idempotent_noop is True
    assert ctx.chunk_count == 1
    assert ctx.vector_count == 1
    assert ctx.no_duplicate_side_effects is True
    # Should not have called the repository
    assert len(doc_repo.saved) == 0


def test_save_step_uses_unit_of_work_transaction() -> None:
    doc_repo = _FakeDocRepo()
    uow = SimpleNamespace()
    uow.begin = lambda: None
    uow.commit = lambda: None
    uow.rollback = lambda: None

    step = SaveStep(
        document_repository=doc_repo,
        chunk_repository=None,
        vector_write=None,
        config=None,
        unit_of_work=uow,
    )
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        version=SimpleNamespace(document_id='doc1', state='processing'),
        chunks=['chunk1'],
        chunk_entities=[SimpleNamespace(chunk_id='c1')],
        vectors=[[0.1, 0.2]],
        metrics=[],
        document_tables=[],
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.status == 'committed'
