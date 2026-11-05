"""Upload HTTP surface: persisted identity, queue signal, and real failures (#233)."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.adapters.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from finsight.adapters.storage.s3_storage import S3Storage
from finsight.application.ingest_document import UploadDocument
from finsight.core.types import CompanyId
from finsight.entrypoints.api import upload as upload_entrypoint
from finsight.entrypoints.api._shared import _BadRequestError

COMPANY = CompanyId('company-a')


class FakeStorageClient:
    def generate_presigned_url(self, client_method: str, params: dict, expires_in: int) -> str:
        return f'https://example.test/{params["Key"]}?expires={expires_in}'


class FakeQueue:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.sent.append((args, kwargs))
        return {'MessageId': f'msg-{len(self.sent)}'}


class FailingQueue:
    async def send(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        raise RuntimeError('queue is not available')


def _use_case(
    repository: PostgresDocumentRepository | None = None,
    queue: Any = None,
) -> UploadDocument:
    return UploadDocument(
        document_repository=repository or PostgresDocumentRepository(),
        object_storage=S3Storage(
            client=FakeStorageClient(), bucket='test-docs', region='us-east-1'
        ),
        queue=queue,
    )


def _payload(**overrides: Any) -> dict[str, Any]:
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


class TestUploadHttpSurface:
    async def test_valid_upload_returns_identity_and_enqueued_signal(self) -> None:
        repository = PostgresDocumentRepository()
        queue = FakeQueue()

        response = await upload_entrypoint._handle(
            payload=_payload(), use_case=_use_case(repository, queue)
        )

        assert response['document_id']
        assert response['version_id']
        assert response['upload_url'].startswith('https://example.test/')
        assert response['enqueued'] is True
        assert len(queue.sent) == 1

    async def test_uploaded_document_is_readable_from_the_library(self) -> None:
        repository = PostgresDocumentRepository()

        response = await upload_entrypoint._handle(
            payload=_payload(), use_case=_use_case(repository)
        )

        documents = await repository.list_documents(COMPANY)
        assert len(documents) == 1
        assert str(documents[0]['id']) == str(response['document_id'])
        stored = await repository.get_document(COMPANY, response['document_id'])
        assert stored is not None
        assert stored['category'] == 'invoice'
        assert stored['period'] == '2026-Q1'
        assert stored['status'] == 'draft'

    async def test_update_upload_targets_the_existing_document(self) -> None:
        repository = PostgresDocumentRepository()
        use_case = _use_case(repository)
        first = await upload_entrypoint._handle(payload=_payload(), use_case=use_case)

        second = await upload_entrypoint._handle(
            payload=_payload(
                upload_type='update',
                replaces_document_id=first['document_id'],
                file='invoice-v2.pdf',
            ),
            use_case=use_case,
        )

        assert str(second['document_id']) == str(first['document_id'])
        versions = await repository.list_document_versions(COMPANY, first['document_id'])
        assert len(versions) == 2

    async def test_missing_upload_type_still_returns_validation(self) -> None:
        payload = _payload()
        payload.pop('upload_type')

        with pytest.raises(_BadRequestError):
            await upload_entrypoint._handle(payload=payload, use_case=_use_case())

    async def test_queue_failure_is_reported_as_not_enqueued(self) -> None:
        repository = PostgresDocumentRepository()

        response = await upload_entrypoint._handle(
            payload=_payload(), use_case=_use_case(repository, FailingQueue())
        )

        assert response['enqueued'] is False
        assert await repository.list_documents(COMPANY) != []
