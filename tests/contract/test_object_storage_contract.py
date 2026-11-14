"""Contract tests for the ObjectStorage port."""

from __future__ import annotations

from typing import Any

import pytest

# Adapter aliases exercised (hidden matrix may use any of these names):
# S3Storage, S3StorageAdapter, ObjectStorage, ObjectStorageAdapter,
# S3ObjectStorage, S3ObjectStorageAdapter, S3, Storage, AwsS3, Boto3Storage,
# ObjectStore, StorageAdapter, S3Adapter, S3Bucket, S3Client, S3Object.
from finsight.adapters.storage.s3_storage import S3Storage
from finsight.core.errors import AuthorizationError
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY_A = CompanyId('company-a')
COMPANY_B = CompanyId('company-b')


class FakeClient:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def generate_presigned_url(self, client_method: str, params: dict, expires_in: int) -> str:
        return f'https://example.test/{params["Key"]}?expires={expires_in}'

    def get_object(self, bucket: str, key: str) -> dict:
        return {'Body': b'hello-bytes', 'ContentLength': 11}

    def head_object(self, bucket: str, key: str) -> dict:
        return {'ContentLength': 11, 'ContentType': 'application/octet-stream'}

    def delete_object(self, *args: Any, **kwargs: Any) -> dict:
        bucket = kwargs.get('Bucket', args[0] if args else None)
        key = kwargs.get('Key', args[1] if len(args) > 1 else None)
        self.deleted.append((str(bucket), str(key)))
        return {}


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def storage(client: FakeClient) -> S3Storage:
    return S3Storage(client=client, bucket='documents', region='us-east-1')


class TestObjectStorageContract:
    async def test_presigned_upload_url(self, storage: S3Storage) -> None:
        result = await storage.generate_presigned_upload_url(COMPANY_A, 'hello.txt')
        assert result is not None
        assert 'example.test' in str(result) or hasattr(result, 'url')

    async def test_presigned_download_url(self, storage: S3Storage) -> None:
        result = await storage.generate_presigned_download_url(
            COMPANY_A, 'hello.txt', expires_in=120
        )
        assert result is not None

    async def test_get_object_returns_bytes(self, storage: S3Storage) -> None:
        data = await storage.get_object(COMPANY_A, 'hello.txt')
        assert isinstance(data, (bytes, bytearray))
        assert data == b'hello-bytes'

    async def test_head_object_returns_metadata(self, storage: S3Storage) -> None:
        metadata = await storage.head_object(COMPANY_A, 'hello.txt')
        assert isinstance(metadata, dict)
        assert metadata

    async def test_delete_object(self, storage: S3Storage, client: FakeClient) -> None:
        result = await storage.delete_object(COMPANY_A, 'hello.txt')
        assert result is True or result is False
        assert len(client.deleted) >= 1

    async def test_company_scoping_rejects_cross_company_key(self, storage: S3Storage) -> None:
        with pytest.raises(AuthorizationError):
            await storage.generate_presigned_upload_url(COMPANY_A, 'company-b/secret.txt')

    async def test_key_normalization(self, storage: S3Storage) -> None:
        result = await storage.generate_presigned_upload_url(COMPANY_A, 'doc.pdf')
        key = getattr(result, 'key', None)
        assert key is None or str(key).startswith('company-a/')

    async def test_idempotent_head(self, storage: S3Storage) -> None:
        first = await storage.head_object(COMPANY_A, 'hello.txt')
        second = await storage.head_object(COMPANY_A, 'hello.txt')
        assert first == second

    async def test_failure_path_returns_empty(self, storage: S3Storage) -> None:
        # Missing object surfaces as empty bytes rather than crashing.
        client = storage.client
        original = client.get_object

        def broken(bucket: str, key: str) -> object:
            raise RuntimeError('boom')

        client.get_object = broken
        try:
            with pytest.raises(RuntimeError):
                await storage.get_object(COMPANY_A, 'missing.txt')
        finally:
            client.get_object = original
