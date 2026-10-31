import asyncio
from datetime import UTC, datetime, timedelta

from finsight.application.source_viewer.source_viewer import SourceViewer


class _FakeDocRepo:
    def __init__(self, versions) -> None:
        self.versions = versions

    async def get_document_version(self, company_id: object, version_id: object) -> object:
        return self.versions.get(str(version_id))

    async def list_document_versions(self, company_id: object, document_id: object = None) -> list[object]:
        if document_id is None:
            return list(self.versions.values())
        return [v for v in self.versions.values() if str(v.get('document_id')) == str(document_id)]

    async def get_latest_committed_version(self, company_id: object, document_id: object = None) -> object:
        cands = [
            v
            for v in self.versions.values()
            if (document_id is None or str(v.get('document_id')) == str(document_id))
            and v.get('state') == 'committed'
        ]
        return cands[-1] if cands else None


class _FakeChunkRepo:
    async def list_chunks_by_version(self, company_id: object, version_id: object, include_inactive: bool = False) -> list[object]:
        return [
            {
                'chunk_id': 'c1',
                'text': 'sensitive document text',
                'version_id': version_id,
                'page_number': 1,
                'is_active': True,
                'needs_review': False,
            }
        ]


def test_source_viewer_allowed_denied_missing_removed_newer() -> None:
    async def run() -> None:
        cid = 'c1'
        v1 = {
            'id': 'v1',
            'document_id': 'd1',
            'company_id': cid,
            'state': 'committed',
            'version': 1,
            'title': 'Doc',
            'created_at': datetime.now(UTC),
        }
        v2 = {
            'id': 'v2',
            'document_id': 'd1',
            'company_id': cid,
            'state': 'committed',
            'version': 2,
            'title': 'Doc',
            'created_at': datetime.now(UTC) + timedelta(days=1),
        }

        # allowed + newer available
        repo = _FakeDocRepo({'v1': v1, 'v2': v2})
        sv = SourceViewer(
            config=None,
            document_repository=repo,
            chunk_repository=_FakeChunkRepo(),
            company_id=cid,
            role='analyst',
            permissions={'financial': ['read']},
            access_scope=['financial'],
        )
        res = await sv.run(company_id=cid, document_version='v1')
        assert res.status == 'available'
        assert res.newer_version_available is True
        assert 'sensitive document text' in (res.text or '')

        # denied
        denied_repo = _FakeDocRepo({'v1': v1})
        sv_denied = SourceViewer(
            config=None,
            document_repository=denied_repo,
            chunk_repository=_FakeChunkRepo(),
            company_id=cid,
            role='system_admin',
            permissions={},
            access_scope=['financial'],
        )
        res_denied = await sv_denied.run(company_id=cid, document_version='v1')
        assert res_denied.status == 'not_available'
        assert res_denied.text == ''
        assert not getattr(res_denied, 'newer_version_available', False)

        # missing
        res_missing = await sv.run(company_id=cid, document_version='nope')
        assert res_missing.status == 'not_available'

        # removed state blocked
        removed = {
            'id': 'vr',
            'document_id': 'd1',
            'company_id': cid,
            'state': 'removed',
            'version': 1,
            'created_at': datetime.now(UTC),
        }
        repo_removed = _FakeDocRepo({'vr': removed})
        sv_removed = SourceViewer(
            config=None,
            document_repository=repo_removed,
            chunk_repository=_FakeChunkRepo(),
            company_id=cid,
            role='analyst',
            permissions={'financial': ['read']},
            access_scope=['financial'],
        )
        res_removed = await sv_removed.run(company_id=cid, document_version='vr')
        assert res_removed.status == 'not_available'

        # expired superseded
        expired = {
            'id': 'vx',
            'document_id': 'd1',
            'company_id': cid,
            'state': 'superseded',
            'version': 1,
            'created_at': datetime.now(UTC) - timedelta(days=500),
        }
        repo_exp = _FakeDocRepo({'vx': expired})
        sv_exp = SourceViewer(
            config=None,
            document_repository=repo_exp,
            chunk_repository=_FakeChunkRepo(),
            company_id=cid,
            role='analyst',
            permissions={'financial': ['read']},
            access_scope=['financial'],
        )
        res_exp = await sv_exp.run(company_id=cid, document_version='vx')
        assert res_exp.status == 'not_available'

    asyncio.run(run())
