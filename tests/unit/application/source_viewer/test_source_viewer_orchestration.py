"""Behavioral tests for source-viewer orchestration."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.source_viewer import SourceViewer


class _Repo:
    async def get_version(
        self, company_id: Any = None, version_id: Any = None, *args: Any, **kwargs: Any
    ) -> Any:
        return SimpleNamespace(
            state='committed',
            document_id='doc1',
            id='v1',
            document_title='Doc',
            company_id=company_id,
        )

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(title='Doc')

    async def list_versions(self, *args: Any, **kwargs: Any) -> Any:
        return []

    async def get_latest_version(self, *args: Any, **kwargs: Any) -> Any:
        return None


def _viewer() -> SourceViewer:
    return SourceViewer(
        company_id='co1',
        document_repository=_Repo(),
        signing_key='secret-key-1234567890-abcdefghijklmnopqrstuvwxyz',  # pragma: allowlist secret
    )


def test_source_viewer_view_success() -> None:
    viewer = _viewer()
    result = asyncio.run(viewer.view(company_id='co1', document_id='doc1', document_version='v1'))
    assert result.outcome == 'success'
    assert result.document_id == 'doc1'


def test_source_viewer_view_original_path() -> None:
    viewer = _viewer()
    result = asyncio.run(
        viewer.view_original(company_id='co1', document_id='doc1', document_version='v1')
    )
    assert result.outcome in ('success', 'not_available')
