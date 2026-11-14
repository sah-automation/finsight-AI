"""Regression test for run_pipeline early-break gate (issue #241)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.ingest_document import IngestionPipeline
from finsight.domain.value_objects.reader_result import ReaderResult


class _FakeReader:
    def __init__(self, text: str = 'doc text') -> None:
        self._result = ReaderResult(text=text, tables=[], page_numbers=[], confidence=None)

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


pytestmark = pytest.mark.unit


def _context(text: str = 'hello world') -> tuple[IngestionPipeline, SimpleNamespace]:
    reader = _FakeReader(text=text)
    pipeline = IngestionPipeline(reader=reader, config=None, delta_tracking=True)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='',
    )
    return pipeline, ctx


def test_non_empty_read_runs_all_six_steps_and_completes() -> None:
    pipeline, ctx = _context('hello world')
    result = asyncio.run(pipeline.run_pipeline(ctx))

    assert isinstance(result, dict)
    assert result.get('status') == 'completed'
    steps = [r.get('step') for r in result.get('pipeline', []) if isinstance(r, dict)]
    assert steps == ['read', 'delta', 'chunk', 'embed', 'save', 'cascade']
    # chunk count judged from chunk step result
    assert result.get('chunks', 0) > 0


def test_zero_extraction_runs_only_read_and_fails() -> None:
    pipeline, ctx = _context('')
    result = asyncio.run(pipeline.run_pipeline(ctx))

    assert isinstance(result, dict)
    assert result.get('status') == 'failed'
    steps = [r.get('step') for r in result.get('pipeline', []) if isinstance(r, dict)]
    assert steps == ['read']
