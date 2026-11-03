"""Black-box characterization tests for the current source-view flow.

Driven only through the public ``SourceViewer`` entry the router uses.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from finsight.application.source_viewer import SourceViewer
from finsight.core.security.citation_locator import mint_citation_locator

SECRET = 'secret-key-1234567890-abcdefghijklmnopqrstuvwxyz'  # pragma: allowlist secret


class _DocRepo:
    def __init__(self, versions: dict[str, Any] | None = None) -> None:
        self.versions = versions or {}

    async def get_document_version(self, company_id: Any, version_id: Any) -> Any:
        return self.versions.get(str(version_id))

    async def list_document_versions(self, company_id: Any, document_id: Any = None) -> list[Any]:
        if document_id is None:
            return list(self.versions.values())
        return [v for v in self.versions.values() if str(v.get('document_id')) == str(document_id)]

    async def get_latest_committed_version(self, company_id: Any, document_id: Any = None) -> Any:
        candidates = [
            v
            for v in self.versions.values()
            if (document_id is None or str(v.get('document_id')) == str(document_id))
            and v.get('state') == 'committed'
        ]
        return candidates[-1] if candidates else None

    async def get_document(self, company_id: Any, document_id: Any) -> Any:
        return {'title': 'Doc', 'document_id': document_id}


class _NoDocRepo(_DocRepo):
    async def get_document(self, company_id: Any, document_id: Any) -> Any:
        return None


class _ChunkRepo:
    def __init__(
        self,
        *,
        chunks: list[dict[str, Any]] | None = None,
        by_id: dict[str, dict[str, Any]] | None = None,
        fail: bool = False,
    ) -> None:
        self._chunks = chunks or []
        self._by_id = by_id or {}
        self._fail = fail

    async def list_chunks_by_version(
        self, company_id: Any, version_id: Any, include_inactive: bool = False
    ) -> list[Any]:
        if self._fail:
            raise RuntimeError('chunk repo failure')
        return [dict(c) for c in self._chunks if str(c.get('version_id')) == str(version_id)]

    async def get_chunk(self, company_id: Any, chunk_id: Any) -> Any:
        if self._fail:
            raise RuntimeError('chunk repo failure')
        return self._by_id.get(str(chunk_id))


class _TableRepo:
    def __init__(self, tables: list[dict[str, Any]] | None = None, *, fail: bool = False) -> None:
        self._tables = tables or []
        self._fail = fail

    async def list_document_tables(
        self,
        company_id: Any,
        version_id: Any = None,
        document_id: Any = None,
        page_number: Any = None,
    ) -> list[Any]:
        if self._fail:
            raise RuntimeError('table repo failure')
        rows = list(self._tables)
        if page_number is not None:
            out = []
            for t in rows:
                tp = t.get('page', t.get('page_number'))
                if tp is None or int(tp) == int(page_number):
                    out.append(dict(t))
            return out
        return [dict(t) for t in rows]

    async def get_document_table(self, company_id: Any, table_id: Any) -> Any:
        if self._fail:
            raise RuntimeError('table repo failure')
        for t in self._tables:
            if str(t.get('table_id', t.get('id'))) == str(table_id):
                return dict(t)
        return None


class _Storage:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[Any] = []
        self._fail = fail

    async def generate_presigned_download_url(
        self, company_id: Any, key: Any, expires_in: Any = None, **kwargs: Any
    ) -> str:
        self.calls.append((company_id, key, expires_in))
        if self._fail:
            raise RuntimeError('storage failure')
        return f'https://example.invalid/{key}?expires={expires_in}'


class _Audit:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def append(self, **kwargs: Any) -> None:
        self.records.append(dict(kwargs))

    async def record(self, **kwargs: Any) -> None:
        self.records.append(dict(kwargs))


def _committed_version(
    vid: str = 'v1',
    did: str = 'd1',
    cid: str = 'c1',
    category: str = 'financial',
    storage_key: str | None = 'storage/key.pdf',
) -> dict[str, Any]:
    row: dict[str, Any] = {
        'id': vid,
        'document_id': did,
        'company_id': cid,
        'state': 'committed',
        'version': 1,
        'title': 'Doc',
        'category': category,
        'created_at': datetime.now(UTC),
    }
    if storage_key is not None:
        row['storage_key'] = storage_key
    return row


from finsight.application.source_viewer.steps import (
    AuditStep,
    AuthorizeStep,
    FetchContentStep,
    FetchOriginalStep,
    ResolveCitationStep,
    ResolveVersionStep,
)


class _Viewer(SourceViewer):
    def __init__(
        self, *args: Any, _permissions: Any = None, _access_scope: Any = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._permissions = _permissions
        self._access_scope = _access_scope

    async def run(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        kwargs.setdefault('company_id', 'c1')
        kwargs.setdefault('role', 'analyst')
        if 'permissions' not in kwargs:
            kwargs['permissions'] = (
                self._permissions
                if self._permissions is not None
                else {'financial': ['read', 'view_original']}
            )
        if 'access_scope' not in kwargs:
            kwargs['access_scope'] = (
                self._access_scope if self._access_scope is not None else ['financial']
            )
        return await super().run(*args, **kwargs)


def _viewer(
    *,
    doc_repo: Any = None,
    chunk_repo: Any = None,
    table_repo: Any = None,
    storage: Any = None,
    audit: Any = None,
    permissions: Any = None,
    access_scope: list[str] | None = None,
    config: Any = None,
) -> SourceViewer:
    # Build steps from the supplied adapters (parity with the legacy fused flow).
    return _Viewer(
        authorize_step=AuthorizeStep(config=config),
        resolve_citation_step=ResolveCitationStep(signing_key=SECRET),
        resolve_version_step=ResolveVersionStep(
            document_repository=doc_repo, version_retention_days=365
        ),
        fetch_content_step=FetchContentStep(
            chunk_repository=chunk_repo, table_repository=table_repo
        ),
        fetch_original_step=FetchOriginalStep(
            object_storage=storage, document_repository=doc_repo, ttl=300
        ),
        audit_step=AuditStep(audit_log=audit),
        _permissions=permissions,
        _access_scope=access_scope if access_scope is not None else ['financial'],
    )


def test_table_resolved_by_table_id() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()
        doc_repo = _DocRepo({'v1': v1})
        table = {
            'table_id': 'table-1',
            'id': 'table-1',
            'page': 1,
            'payload': {'rows': [['a', 'b']]},
            'needs_review': False,
        }
        table_repo = _TableRepo([table])
        viewer = _viewer(doc_repo=doc_repo, table_repo=table_repo, audit=_Audit())
        res = await viewer.run(company_id=cid, document_version='v1', table_id='table-1', page=1)
        assert res.status == 'available'
        assert res.table is not None
        assert res.table.get('table_id') == 'table-1'
        assert res.content_type == 'table'

    asyncio.run(run())


def test_tables_attached_to_page_aggregate() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()
        doc_repo = _DocRepo({'v1': v1})
        table = {
            'table_id': 't1',
            'id': 't1',
            'page': 1,
            'payload': {'rows': [['x']]},
            'needs_review': False,
        }
        table_repo = _TableRepo([table])
        chunk_repo = _ChunkRepo(
            chunks=[
                {
                    'chunk_id': 'c9',
                    'text': 'hello',
                    'version_id': 'v1',
                    'page_number': 1,
                    'is_active': True,
                    'needs_review': False,
                }
            ]
        )
        viewer = _viewer(
            doc_repo=doc_repo, chunk_repo=chunk_repo, table_repo=table_repo, audit=_Audit()
        )
        res = await viewer.run(company_id=cid, document_version='v1', page=1)
        assert res.status == 'available'
        assert isinstance(res.tables, list) and len(res.tables) >= 1
        assert res.tables[0].get('table_id') == 't1'

    asyncio.run(run())


def test_page_filtered_aggregate_chunk_text_and_single_chunk() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()
        doc_repo = _DocRepo({'v1': v1})
        chunks = [
            {
                'chunk_id': 'c1',
                'text': 'first',
                'version_id': 'v1',
                'page_number': 1,
                'is_active': True,
                'needs_review': False,
            },
            {
                'chunk_id': 'c2',
                'text': 'second',
                'version_id': 'v1',
                'page_number': 1,
                'is_active': True,
                'needs_review': False,
            },
            {
                'chunk_id': 'c3',
                'text': 'other',
                'version_id': 'v1',
                'page_number': 2,
                'is_active': True,
                'needs_review': False,
            },
        ]
        chunk_repo = _ChunkRepo(chunks=chunks, by_id={c['chunk_id']: c for c in chunks})
        viewer = _viewer(doc_repo=doc_repo, chunk_repo=chunk_repo, audit=_Audit())
        # aggregate page 1
        res = await viewer.run(company_id=cid, document_version='v1', page=1)
        assert res.status == 'available'
        assert 'first' in (res.text or '') and 'second' in (res.text or '')
        assert 'other' not in (res.text or '')
        # single chunk lookup
        res2 = await viewer.run(company_id=cid, document_version='v1', chunk_id='c2', page=1)
        assert res2.status == 'available'
        assert (res2.text or '').strip() == 'second'

    asyncio.run(run())


def test_original_document_link_success_and_missing() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()

        # success
        storage = _Storage()
        audit = _Audit()
        chunk_repo = _ChunkRepo(chunks=[])
        viewer = _viewer(
            doc_repo=_DocRepo({'v1': v1}), chunk_repo=chunk_repo, storage=storage, audit=audit
        )
        res = await viewer.run(
            company_id=cid,
            document_version='v1',
            category='financial',
            original=True,
        )
        assert res.status == 'available'
        assert res.original_link is not None
        assert len(storage.calls) >= 1

        # missing storage key: version without any resolvable key and no title
        no_key = _committed_version(storage_key=None)
        no_key['title'] = None
        no_key['document_id'] = None
        doc_repo2 = _NoDocRepo({'v1': no_key})
        storage2 = _Storage()
        viewer2 = _viewer(
            doc_repo=doc_repo2, chunk_repo=_ChunkRepo(chunks=[]), storage=storage2, audit=_Audit()
        )
        res2 = await viewer2.run(
            company_id=cid, document_version='v1', category='financial', original=True
        )
        assert res2.status == 'not_available'
        assert res2.original_link is None

        # missing storage adapter
        viewer3 = _viewer(
            doc_repo=_DocRepo({'v1': v1}),
            chunk_repo=_ChunkRepo(chunks=[]),
            storage=None,
            audit=_Audit(),
        )
        res3 = await viewer3.run(
            company_id=cid, document_version='v1', category='financial', original=True
        )
        assert res3.status == 'not_available'
        assert res3.original_link is None

    asyncio.run(run())


def test_tampered_signed_locator_not_available() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()
        doc_repo = _DocRepo({'v1': v1})
        proper = mint_citation_locator(
            SECRET, document_id='d1', document_version='v1', chunk_id='c1'
        )
        # tamper
        tampered = proper[:-3] + 'abc'
        viewer = _viewer(doc_repo=doc_repo, chunk_repo=_ChunkRepo(chunks=[]), audit=_Audit())
        res = await viewer.run(company_id=cid, citation=tampered, document_version='v1')
        assert res.status == 'not_available'

    asyncio.run(run())


def test_audit_record_captured_success_and_denial() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()
        doc_repo = _DocRepo({'v1': v1})
        chunks = [
            {
                'chunk_id': 'cx',
                'text': 'hello',
                'version_id': 'v1',
                'page_number': 1,
                'is_active': True,
                'needs_review': False,
            }
        ]
        chunk_repo = _ChunkRepo(chunks=chunks)
        audit = _Audit()
        viewer = _viewer(doc_repo=doc_repo, chunk_repo=chunk_repo, audit=audit)
        res = await viewer.run(company_id=cid, document_version='v1', page=1)
        assert res.status == 'available'
        assert len(audit.records) >= 1

        audit2 = _Audit()
        viewer_denied = _Viewer(
            authorize_step=AuthorizeStep(config=None),
            resolve_citation_step=ResolveCitationStep(signing_key=SECRET),
            resolve_version_step=ResolveVersionStep(document_repository=_DocRepo({'v1': v1})),
            fetch_content_step=FetchContentStep(chunk_repository=_ChunkRepo(chunks=chunks)),
            fetch_original_step=FetchOriginalStep(
                object_storage=None, document_repository=_DocRepo({'v1': v1}), ttl=300
            ),
            audit_step=AuditStep(audit_log=audit2),
            _permissions={},
            _access_scope=['financial'],
        )
        res2 = await viewer_denied.run(
            company_id=cid, role='system_admin', document_version='v1', page=1
        )
        assert res2.status == 'not_available'
        assert len(audit2.records) >= 1

    asyncio.run(run())


def test_result_shape_not_available_and_error() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = _committed_version()

        # not-available
        doc_repo = _DocRepo({'v1': v1})
        viewer = _Viewer(
            authorize_step=AuthorizeStep(config=None),
            resolve_citation_step=ResolveCitationStep(signing_key=SECRET),
            resolve_version_step=ResolveVersionStep(document_repository=doc_repo),
            fetch_content_step=FetchContentStep(chunk_repository=_ChunkRepo(chunks=[])),
            fetch_original_step=FetchOriginalStep(
                object_storage=None, document_repository=doc_repo, ttl=300
            ),
            audit_step=AuditStep(audit_log=None),
        )
        res = await viewer.run(company_id=cid, document_version='nope')
        assert res.status == 'not_available'
        assert res.outcome == 'not_available'
        assert res.result == 'not_available'

        # error via failing chunk repo
        doc_repo2 = _DocRepo({'v1': v1})
        chunk_repo2 = _ChunkRepo(fail=True, chunks=[])
        viewer2 = _viewer(doc_repo=doc_repo2, chunk_repo=chunk_repo2, audit=_Audit())
        res2 = await viewer2.run(company_id=cid, document_version='v1', page=1)
        assert res2.status == 'not_available'
        assert res2.outcome == 'error'
        assert res2.result == 'not_available'

    asyncio.run(run())
