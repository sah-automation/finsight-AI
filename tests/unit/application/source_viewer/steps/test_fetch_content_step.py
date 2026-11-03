from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.fetch_content_step import FetchContentStep


class _ChunkRepo:
    def __init__(self, *, chunks=None, by_id=None) -> None:
        self._chunks = chunks or []
        self._by_id = by_id or {}

    async def list_chunks_by_version(
        self, company_id, version_id, include_inactive=False
    ) -> list[Any]:
        return [dict(c) for c in self._chunks if str(c.get('version_id')) == str(version_id)]

    async def get_chunk(self, company_id, chunk_id) -> Any:
        v = self._by_id.get(str(chunk_id))
        return dict(v) if isinstance(v, dict) else v


class _TableRepo:
    def __init__(self, tables=None) -> None:
        self._tables = tables or []

    async def list_document_tables(
        self, company_id, version_id=None, document_id=None, page_number=None
    ) -> Any:
        rows = [dict(t) for t in self._tables]
        if page_number is not None:
            out = []
            for t in rows:
                tp = t.get('page', t.get('page_number'))
                if tp is None or int(tp) == int(page_number):
                    out.append(t)
            return out
        return rows

    async def get_document_table(self, company_id, table_id) -> Any:
        for t in self._tables:
            if str(t.get('table_id', t.get('id'))) == str(table_id):
                return dict(t)
        return None


def _step(chunk_repo=None, table_repo=None) -> FetchContentStep:
    return FetchContentStep(chunk_repository=chunk_repo, table_repository=table_repo)


def test_chunk_found() -> None:
    chunk = {
        'chunk_id': 'c1',
        'text': 'hello',
        'version_id': 'v1',
        'page_number': 1,
        'is_active': True,
        'needs_review': False,
    }
    repo = _ChunkRepo(by_id={'c1': chunk})
    ctx = SourceViewerContext(company_id='co', version_id='v1', chunk_id='c1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.text == 'hello'
    assert ctx.content_type == 'text'
    assert ctx.needs_review is False


def test_chunk_missing() -> None:
    repo = _ChunkRepo(by_id={})
    ctx = SourceViewerContext(company_id='co', version_id='v1', chunk_id='missing', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'not_available'


def test_chunk_wrong_version() -> None:
    chunk = {
        'chunk_id': 'c1',
        'text': 'hello',
        'version_id': 'v2',
        'page_number': 1,
        'is_active': True,
    }
    repo = _ChunkRepo(by_id={'c1': chunk})
    ctx = SourceViewerContext(company_id='co', version_id='v1', chunk_id='c1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'not_available'


def test_chunk_page_mismatch() -> None:
    chunk = {
        'chunk_id': 'c1',
        'text': 'hello',
        'version_id': 'v1',
        'page_number': 2,
        'is_active': True,
    }
    repo = _ChunkRepo(by_id={'c1': chunk})
    ctx = SourceViewerContext(company_id='co', version_id='v1', chunk_id='c1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'not_available'


def test_table_found_via_list() -> None:
    table = {'table_id': 'table-1', 'id': 'table-1', 'page': 1, 'text': 'tbl', 'needs_review': True}
    trepo = _TableRepo([table])
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    ctx.chunk_id = 'table-1'
    res = asyncio.run(_step(table_repo=trepo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.content_type == 'table'
    assert ctx.text == 'tbl'
    assert ctx.needs_review is True
    assert ctx.table_payload['table_id'] == 'table-1'


def test_table_found_via_get() -> None:
    table = {
        'table_id': 'table-2',
        'id': 'table-2',
        'page': 1,
        'text': 'tbl2',
        'needs_review': False,
    }

    class Repo(_TableRepo):
        async def list_document_tables(
            self, company_id, version_id=None, document_id=None, page_number=None
        ) -> Any:
            return []

        async def get_document_table(self, company_id, table_id) -> Any:
            if str(table_id) == 'table-2':
                return dict(table)
            return None

    trepo = Repo([])
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    ctx.chunk_id = 'table-2'
    res = asyncio.run(_step(table_repo=trepo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.content_type == 'table'
    assert ctx.text == 'tbl2'


def test_table_missing() -> None:
    trepo = _TableRepo([])
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    ctx.chunk_id = 'table-missing'
    res = asyncio.run(_step(table_repo=trepo).run(ctx))
    assert res.kind == 'not_available'


def test_page_filter_across_chunks() -> None:
    chunks = [
        {
            'chunk_id': 'a',
            'text': 'first',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': True,
            'needs_review': False,
        },
        {
            'chunk_id': 'b',
            'text': 'second',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': True,
            'needs_review': False,
        },
        {
            'chunk_id': 'c',
            'text': 'other',
            'version_id': 'v1',
            'page_number': 2,
            'is_active': True,
            'needs_review': False,
        },
    ]
    repo = _ChunkRepo(chunks=chunks)
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'continue'
    assert 'first' in ctx.text and 'second' in ctx.text
    assert 'other' not in ctx.text


def test_inactive_chunks_dropped() -> None:
    chunks = [
        {
            'chunk_id': 'a',
            'text': 'active',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': True,
            'needs_review': False,
        },
        {
            'chunk_id': 'b',
            'text': 'inactive',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': False,
            'needs_review': False,
        },
    ]
    repo = _ChunkRepo(chunks=chunks)
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'continue'
    assert 'active' in ctx.text
    assert 'inactive' not in ctx.text


def test_content_type_text_vs_table() -> None:
    chunks = [
        {
            'chunk_id': 'a',
            'text': 'hello',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': True,
            'needs_review': False,
        }
    ]
    table = {'table_id': 't1', 'page': 1, 'payload': {'rows': [['x']]}, 'needs_review': False}
    repo = _ChunkRepo(chunks=chunks)
    trepo = _TableRepo([table])
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    res = asyncio.run(_step(chunk_repo=repo, table_repo=trepo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.content_type == 'text'

    chunks2 = [
        {
            'chunk_id': 'a',
            'text': '',
            'version_id': 'v1',
            'page_number': 1,
            'is_active': True,
            'needs_review': False,
        }
    ]
    repo2 = _ChunkRepo(chunks=chunks2)
    ctx2 = SourceViewerContext(company_id='co', version_id='v1', page=1)
    res2 = asyncio.run(_step(chunk_repo=repo2, table_repo=trepo).run(ctx2))
    assert res2.kind == 'continue'
    assert ctx2.content_type == 'table'


def test_empty_content() -> None:
    repo = _ChunkRepo(chunks=[])
    ctx = SourceViewerContext(company_id='co', version_id='v1', page=1)
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.text == ''


def test_highlight_from_locator_claims() -> None:
    ctx = SourceViewerContext(
        company_id='co', version_id='v1', page=1, locator_payload={'s': 2, 'e': 5}
    )
    repo = _ChunkRepo(chunks=[])
    res = asyncio.run(_step(chunk_repo=repo).run(ctx))
    assert res.kind == 'continue'
    assert ctx.highlight is not None
    assert ctx.highlight['start_char'] == 2
    assert ctx.highlight['end_char'] == 5
