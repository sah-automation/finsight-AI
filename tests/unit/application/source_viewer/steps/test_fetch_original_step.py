"""Unit tests for the original-document link step."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.fetch_original_step import FetchOriginalStep

TTL_SECONDS = 900


class _Storage:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[Any, Any, Any]] = []
        self._fail = fail

    async def generate_presigned_download_url(
        self, company_id: Any, key: str, *, expires_in: Any = None, **kwargs: Any
    ) -> str:
        self.calls.append((company_id, key, expires_in))
        if self._fail:
            raise RuntimeError('storage failure')
        return f'https://example.invalid/{key}?expires={expires_in}'


class _DocRepo:
    async def get_document(self, company_id: Any, document_id: Any, **kwargs: Any) -> Any:
        return None


def _step(storage: Any = None, repo: Any = None) -> FetchOriginalStep:
    return FetchOriginalStep(
        object_storage=storage,
        document_repository=repo if repo is not None else _DocRepo(),
        ttl_seconds=TTL_SECONDS,
    )


def _context(**overrides: Any) -> SourceViewerContext:
    values: dict[str, Any] = {
        'company_id': 'c1',
        'document_id': 'd1',
        'version_id': 'v1',
        'original_requested': True,
        'original_available': True,
        'version_obj': {'id': 'v1', 'document_id': 'd1', 'storage_key': 'c1/source.pdf'},
    }
    values.update(overrides)
    return SourceViewerContext(**values)


def test_signed_url_is_written_to_context() -> None:
    storage = _Storage()
    ctx = _context()
    result = asyncio.run(_step(storage).run(ctx))
    assert result.kind == 'continue'
    assert ctx.signed_original_link == 'https://example.invalid/c1/source.pdf?expires=900'
    assert storage.calls == [('c1', 'c1/source.pdf', TTL_SECONDS)]


def test_explicit_storage_key_wins() -> None:
    storage = _Storage()
    ctx = _context(storage_key='explicit/key.pdf')
    asyncio.run(_step(storage).run(ctx))
    assert storage.calls[0][1] == 'explicit/key.pdf'


def test_request_ttl_overrides_configured_ttl() -> None:
    storage = _Storage()
    asyncio.run(_step(storage).run(_context(ttl=60)))
    assert storage.calls[0][2] == 60


def test_missing_storage_key_stops() -> None:
    storage = _Storage()
    ctx = _context(version_obj={'id': 'v1', 'document_id': 'd1'}, document_id=None, version_id=None)
    result = asyncio.run(_step(storage).run(ctx))
    assert result.kind == 'not_available'
    assert storage.calls == []


def test_missing_storage_adapter_stops() -> None:
    result = asyncio.run(_step(None).run(_context()))
    assert result.kind == 'not_available'


def test_storage_failure_stops() -> None:
    result = asyncio.run(_step(_Storage(fail=True)).run(_context()))
    assert result.kind == 'not_available'


def test_original_not_requested_continues_without_storage() -> None:
    storage = _Storage()
    ctx = _context(original_requested=False)
    result = asyncio.run(_step(storage).run(ctx))
    assert result.kind == 'continue'
    assert storage.calls == []
    assert ctx.signed_original_link is None


def test_original_not_available_stops() -> None:
    storage = _Storage()
    result = asyncio.run(_step(storage).run(_context(original_available=False)))
    assert result.kind == 'not_available'
    assert storage.calls == []
