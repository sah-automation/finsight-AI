"""Unit tests for the version-resolution step."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.resolve_version_step import ResolveVersionStep

RETENTION_DAYS = 30


class _DocRepo:
    """Fake document repository exposing only the port methods the step uses."""

    def __init__(self, version: Any = None, versions: list[Any] | None = None) -> None:
        self._version = version
        self._versions = versions or []
        self.document_calls: list[Any] = []

    async def get_document_version(self, company_id: Any, version_id: Any, **kwargs: Any) -> Any:
        return self._version

    async def list_document_versions(
        self, company_id: Any, document_id: Any = None, **kwargs: Any
    ) -> list[Any]:
        return list(self._versions)

    async def get_document(self, company_id: Any, document_id: Any, **kwargs: Any) -> Any:
        self.document_calls.append(document_id)
        return {'title': 'Report Q1'}


def _version(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'id': 'v1',
        'document_id': 'd1',
        'company_id': 'c1',
        'state': 'committed',
        'version': 1,
        'title': 'Report Q1',
        'category': 'financial',
        'created_at': datetime.now(UTC),
    }
    row.update(overrides)
    return row


def _step(repo: Any) -> ResolveVersionStep:
    return ResolveVersionStep(document_repository=repo, version_retention_days=RETENTION_DAYS)


def _context(**overrides: Any) -> SourceViewerContext:
    values: dict[str, Any] = {'company_id': 'c1', 'document_id': 'd1', 'version_id': 'v1'}
    values.update(overrides)
    return SourceViewerContext(**values)


def test_committed_version_resolves_metadata() -> None:
    repo = _DocRepo(_version())
    ctx = _context()
    result = asyncio.run(_step(repo).run(ctx))
    assert result.kind == 'continue'
    assert ctx.version_obj is not None
    assert ctx.document_title == 'Report Q1'
    assert ctx.category == 'financial'
    assert ctx.newer_available is False


def test_missing_version_stops() -> None:
    repo = _DocRepo(None)
    result = asyncio.run(_step(repo).run(_context()))
    assert result.kind == 'not_available'


def test_superseded_past_retention_stops() -> None:
    repo = _DocRepo(_version(state='superseded', created_at=datetime.now(UTC) - timedelta(days=90)))
    result = asyncio.run(_step(repo).run(_context()))
    assert result.kind == 'not_available'


def test_superseded_inside_retention_continues() -> None:
    repo = _DocRepo(_version(state='superseded', created_at=datetime.now(UTC) - timedelta(days=1)))
    result = asyncio.run(_step(repo).run(_context()))
    assert result.kind == 'continue'


def test_wrong_company_stops() -> None:
    repo = _DocRepo(_version(company_id='other-company'))
    result = asyncio.run(_step(repo).run(_context()))
    assert result.kind == 'not_available'


def test_blocked_state_stops() -> None:
    repo = _DocRepo(_version(state='processing'))
    result = asyncio.run(_step(repo).run(_context()))
    assert result.kind == 'not_available'


def test_newer_committed_version_is_reported() -> None:
    cited = _version(id='v1', version=1)
    newer = _version(id='v2', version=2)
    repo = _DocRepo(cited, versions=[cited, newer])
    ctx = _context()
    result = asyncio.run(_step(repo).run(ctx))
    assert result.kind == 'continue'
    assert ctx.newer_available is True
    assert ctx.newer_id == 'v2'


def test_title_falls_back_to_document_repository() -> None:
    repo = _DocRepo(_version(title=None))
    ctx = _context()
    result = asyncio.run(_step(repo).run(ctx))
    assert result.kind == 'continue'
    assert ctx.document_title == 'Report Q1'
    assert repo.document_calls == ['d1']
