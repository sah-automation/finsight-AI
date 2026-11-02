from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.ingest_document.read_step import ReadStep
from finsight.domain.value_objects.reader_result import ReaderResult


class _FakeReader:
    def __init__(
        self, text: str = 'doc text', tables=None, page_numbers=None, confidence=None
    ) -> None:
        self._result = ReaderResult(
            text=text,
            tables=tables or [],
            page_numbers=page_numbers or [],
            confidence=confidence,
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


def test_read_step_augments_context_with_reader_result_and_metrics() -> None:
    reader = _FakeReader(text='hello world', tables=[{'rows': [['a', '1']]}], page_numbers=[1])
    step = ReadStep(reader=reader, document_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.reader_result is not None
    assert ctx.reader_result.text == 'hello world'
    assert ctx.metrics is not None
    assert ctx.delta_tracking is True
    assert ctx.branch in ('delta', 'full_reprocess')
    assert ctx.status == 'processing'


def test_read_step_returns_committed_when_version_already_committed() -> None:
    reader = _FakeReader()
    step = ReadStep(reader=reader, document_repository=None, config=None)
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


def test_read_step_extracts_metrics_from_reader_result() -> None:
    tables = [{'rows': [['Revenue', '100'], ['Expenses', '50']]}]
    reader = _FakeReader(text='text', tables=tables)
    step = ReadStep(reader=reader, config=None)
    ctx = SimpleNamespace(company_id='co', version_id='v1', document_id='doc1', key='key')

    asyncio.run(step.run(ctx))

    assert ctx.metrics is not None
    assert len(ctx.metrics) >= 1
