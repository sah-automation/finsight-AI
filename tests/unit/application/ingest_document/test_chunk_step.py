from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.ingest_document.chunk_step import ChunkStep
from finsight.domain.value_objects.reader_result import ReaderResult


class _FakeReader:
    def __init__(self, text: str = 'doc text', tables=None, page_numbers=None) -> None:
        self._result = ReaderResult(
            text=text,
            tables=tables or [],
            page_numbers=page_numbers or [],
        )

    async def read(self, company_id: Any, key: Any, **kwargs: Any) -> ReaderResult:
        return self._result

    async def read_document(self, company_id: Any, key: Any, **kwargs: Any) -> ReaderResult:
        return self._result

    async def extract(self, company_id: Any, key: Any, **kwargs: Any) -> ReaderResult:
        return self._result

    async def parse(self, company_id: Any, key: Any, **kwargs: Any) -> ReaderResult:
        return self._result

    async def extract_text(self, company_id: Any, key: Any, **kwargs: Any) -> ReaderResult:
        return self._result


def test_chunk_step_creates_chunks_and_entities() -> None:
    reader = _FakeReader(text='para one\n\npara two\n\npara three', page_numbers=[1, 1, 2])
    step = ChunkStep(reader=reader, document_repository=None, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.chunks is not None
    assert len(ctx.chunks) == 3
    assert ctx.chunk_entities is not None
    assert len(ctx.chunk_entities) == 3
    assert ctx.chunk_count == 3
    assert ctx.status == 'processing'
    assert ctx.delta_tracking is True


def test_chunk_step_returns_committed_when_version_already_committed() -> None:
    reader = _FakeReader()
    step = ChunkStep(reader=reader, document_repository=None, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        version=SimpleNamespace(state='committed'),
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.committed is True
    assert ctx.idempotent is True
    assert ctx.idempotent_noop is True


def test_chunk_step_tracks_delta_changes_when_enabled() -> None:
    reader = _FakeReader(text='para one\n\npara two', page_numbers=[1, 1])
    step = ChunkStep(reader=reader, document_repository=None, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.changed_chunk_entities is not None
    assert ctx.removed_chunk_ids is not None
    assert ctx.delta_tracking is True
