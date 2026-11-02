from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.ingest_document.delta_step import DeltaStep
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


def test_delta_step_computes_page_hashes_and_diff() -> None:
    reader = _FakeReader(text='page one\n\npage two', page_numbers=[1, 2])
    step = DeltaStep(reader=reader, document_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.reader_result is not None
    assert ctx.page_hashes is not None
    assert len(ctx.page_hashes) == 2
    assert ctx.page_diff is not None
    assert ctx.delta_tracking is True
    assert ctx.branch in ('delta', 'full_reprocess')
    assert ctx.status == 'processing'


def test_delta_step_returns_committed_when_version_already_committed() -> None:
    reader = _FakeReader()
    step = DeltaStep(reader=reader, document_repository=None, config=None)
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


def test_delta_step_loads_existing_reader_data_from_context() -> None:
    reader = _FakeReader(text='new text')
    step = DeltaStep(reader=reader, document_repository=None, config=None)
    existing_result = ReaderResult(text='existing text', tables=[], page_numbers=[1])
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        reader_result=existing_result,
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    # Should use existing reader_result from context
    assert ctx.reader_result is existing_result
