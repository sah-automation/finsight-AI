"""Upload use case persists the parent Document and its version (issue #233)."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.adapters.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from finsight.adapters.storage.s3_storage import S3Storage
from finsight.application.ingest_document import UploadDocument
from finsight.core.types import CompanyId

COMPANY = CompanyId('company-a')


class FakeStorageClient:
    def generate_presigned_url(self, client_method: str, params: dict, expires_in: int) -> str:
        return f'https://example.test/{params["Key"]}?expires={expires_in}'


class FakeQueue:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.sent.append({'args': args, 'kwargs': kwargs})
        return {'MessageId': f'msg-{len(self.sent)}'}


def _storage() -> S3Storage:
    return S3Storage(client=FakeStorageClient(), bucket='test-docs', region='us-east-1')


def _request(**overrides: Any) -> dict[str, Any]:
    payload = {
        'company_id': str(COMPANY),
        'document_category': 'invoice',
        'period': '2026-Q1',
        'status': 'draft',
        'upload_type': 'new',
        'file': 'invoice.pdf',
    }
    payload.update(overrides)
    return payload


class TestUploadPersistsDocument:
    async def test_new_upload_creates_the_document_and_version(self) -> None:
        repository = PostgresDocumentRepository()
        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
        )

        result = await use_case.execute(_request())

        documents = await repository.list_documents(COMPANY)
        assert len(documents) == 1
        document = documents[0]
        assert str(document['id']) == str(result.document_id)
        assert document['category'] == 'invoice'
        assert document['period'] == '2026-Q1'
        assert document['status'] == 'draft'
        assert document['filename'] == 'invoice.pdf'

        version = await repository.get_document_version(COMPANY, result.version_id)
        assert version is not None
        assert str(version.document_id) == str(result.document_id)
        assert version.state == 'received'
        assert version.category == 'invoice'

    async def test_response_identity_is_the_persisted_identity(self) -> None:
        repository = PostgresDocumentRepository()
        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
        )

        result = await use_case.execute(_request())

        stored = await repository.get_document(COMPANY, result.document_id)
        assert stored is not None
        assert str(stored['id']) == str(result.document_id)

    async def test_update_upload_adds_a_version_to_the_existing_document(self) -> None:
        repository = PostgresDocumentRepository()
        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
        )
        first = await use_case.execute(_request())

        second = await use_case.execute(
            _request(
                upload_type='update',
                replaces_document_id=first.document_id,
                file='invoice-v2.pdf',
            )
        )

        documents = await repository.list_documents(COMPANY)
        assert len(documents) == 1
        assert str(second.document_id) == str(first.document_id)
        versions = await repository.list_document_versions(COMPANY, first.document_id)
        assert len(versions) == 2
        assert {str(version.id) for version in versions} == {
            str(first.version_id),
            str(second.version_id),
        }

    async def test_enqueues_exactly_one_ingestion_job_for_the_new_version(self) -> None:
        repository = PostgresDocumentRepository()
        queue = FakeQueue()
        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
            queue=queue,
        )

        result = await use_case.execute(_request())

        assert result.enqueued is True
        assert len(queue.sent) == 1
        assert str(result.version_id) in str(queue.sent[0])

    async def test_queue_failure_reports_not_enqueued(self) -> None:
        repository = PostgresDocumentRepository()

        class FailingQueue:
            async def send(self, *args: Any, **kwargs: Any) -> dict[str, str]:
                raise RuntimeError('queue does not exist')

        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
            queue=FailingQueue(),
        )

        result = await use_case.execute(_request())

        assert result.enqueued is False

    async def test_persistence_failure_leaves_no_document_behind(self) -> None:
        class ExplodingRepository(PostgresDocumentRepository):
            async def create_document(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
                raise RuntimeError('database unavailable')

        repository = ExplodingRepository()
        use_case = UploadDocument(
            document_repository=repository,
            object_storage=_storage(),
        )

        with pytest.raises(RuntimeError, match='database unavailable'):
            await use_case.execute(_request())

        assert await repository.list_documents(COMPANY) == []
