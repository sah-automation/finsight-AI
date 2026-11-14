"""Contract tests for document lifecycle behaviour on the document repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from finsight.adapters.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from finsight.core.types import CompanyId, DocumentId

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


@pytest.fixture
def repository() -> PostgresDocumentRepository:
    return PostgresDocumentRepository()


async def _document(repository: PostgresDocumentRepository) -> str:
    record = await repository.create_document(
        COMPANY,
        id='document-a',
        filename='report.pdf',
        category='financial_statement',
        period='2026-Q1',
    )
    return str(record['id'])


class TestDocumentRepositoryLifecycle:
    async def test_commit_supersedes_the_previous_version(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)
        first = await repository.create_document_version(
            COMPANY, document_id=document_id, state='committed'
        )
        second = await repository.create_document_version(
            COMPANY, document_id=document_id, state='committed'
        )

        changed = await repository.supersede_previous_versions(
            COMPANY, DocumentId(document_id), keep_version_id=second.id
        )

        assert changed == 1
        reloaded = await repository.get_document_version(COMPANY, first.id)
        assert reloaded is not None
        assert reloaded.state == 'superseded'
        latest = await repository.get_latest_committed_version(COMPANY, document_id)
        assert latest is not None
        assert latest.id == second.id

    async def test_soft_delete_hides_the_document_until_restored(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)

        deleted = await repository.soft_delete_document(
            COMPANY, document_id, deleted_by='user-1', reason='duplicate'
        )

        assert deleted is True
        assert await repository.get_document(COMPANY, document_id) is None
        assert len(await repository.list_recycle_bin(COMPANY)) == 1
        assert await repository.restore_document(COMPANY, document_id) is True
        assert await repository.get_document(COMPANY, document_id) is not None
        assert await repository.list_recycle_bin(COMPANY) == []

    async def test_restore_respects_the_retention_window(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)
        await repository.soft_delete_document(COMPANY, document_id)
        record = repository._documents[str(COMPANY)][document_id]
        record['deleted_at'] = datetime.now(UTC) - timedelta(days=31)

        assert await repository.restore_document(COMPANY, document_id, retention_days=30) is False

    async def test_purge_removes_the_document_and_its_versions(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)
        version = await repository.create_document_version(COMPANY, document_id=document_id)
        await repository.soft_delete_document(COMPANY, document_id)

        assert await repository.purge_document(COMPANY, document_id) is True
        assert await repository.get_document(COMPANY, document_id, include_deleted=True) is None
        assert await repository.get_document_version(COMPANY, version.id) is None

    async def test_audit_listing_keeps_superseded_and_deleted_versions(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)
        first = await repository.create_document_version(
            COMPANY, document_id=document_id, state='committed'
        )
        second = await repository.create_document_version(
            COMPANY, document_id=document_id, state='committed'
        )
        await repository.supersede_previous_versions(
            COMPANY, DocumentId(document_id), keep_version_id=second.id
        )
        await repository.soft_delete_document(COMPANY, document_id)

        audit = await repository.list_versions_for_audit(COMPANY, document_id)

        assert {str(version.id) for version in audit} == {str(first.id), str(second.id)}
        assert await repository.list_document_versions(COMPANY, document_id) == []

    async def test_every_lifecycle_operation_is_tenant_scoped(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)

        assert await repository.get_document(OTHER_COMPANY, document_id) is None
        assert await repository.soft_delete_document(OTHER_COMPANY, document_id) is False
        assert await repository.purge_document(OTHER_COMPANY, document_id) is False
        assert await repository.list_recycle_bin(OTHER_COMPANY) == []

    async def test_document_stamp_markers_track_committed_documents(
        self, repository: PostgresDocumentRepository
    ) -> None:
        document_id = await _document(repository)
        await repository.update_document_stamp(COMPANY, document_id, 'stamp-1')

        markers = await repository.document_version_markers(COMPANY)

        assert markers[document_id] == 'stamp-1'
        await repository.soft_delete_document(COMPANY, document_id)
        assert await repository.document_version_markers(COMPANY) == {}
