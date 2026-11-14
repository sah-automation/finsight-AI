# ruff: noqa: F403
# ruff: noqa: PLE0605, ANN401, BLE001, PLR0911, PLR0912, PLR0913
"""S3 adapter implementing the :class:`ObjectStorage` port."""

from __future__ import annotations

import inspect
from typing import Any, cast

import boto3  # type: ignore[import-untyped]

from finsight.core.errors import AuthorizationError, S3Error
from finsight.domain.ports.object_storage import ObjectStorage
from finsight.domain.value_objects.presigned_upload import PresignedUpload

from ._s3_storage_helpers import *
from ._s3_storage_helpers import (
    _as_text,
    _await_value,
    _coerce_str,
    _first,
)


class S3Storage(ObjectStorage):
    """S3 object storage adapter."""

    config: Any = None
    storage_config: Any = None
    _provided_client: Any = None
    _session: Any = None
    bucket: Any = None
    region: Any = None
    endpoint_url: Any = None
    default_download_expires_in: Any = None
    default_expires_in: Any = None
    kms_key_id: Any = None
    _bucket_by_scope: Any = None
    _client_cache: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        from ._s3_storage_init import _init_s3_storage as _m

        _m(self, *args, **kwargs)

    def _get_client(self) -> Any:
        if self._client_cache is not None:
            return self._client_cache
        if self._session is not None:
            try:
                if hasattr(self._session, 'client') and callable(self._session.client):
                    client = self._session.client(
                        's3', region_name=self.region, endpoint_url=self.endpoint_url
                    )
                    self._client_cache = client
                    return client
            except Exception:
                pass
        try:
            client = boto3.client('s3', region_name=self.region, endpoint_url=self.endpoint_url)
            self._client_cache = client
            return client
        except Exception as exc:  # pragma: no cover - boto3 always available
            raise S3Error(f'Unable to create S3 client: {exc}') from exc

    async def health_check(self) -> bool:
        """Return True if the S3 bucket is reachable."""
        client = self._get_client()
        if client is None:
            return False
        bucket = self.bucket
        if not bucket:
            return False
        head_bucket = getattr(client, 'head_bucket', None)
        if not callable(head_bucket):
            return False
        try:
            if inspect.iscoroutinefunction(head_bucket):
                await head_bucket(Bucket=str(bucket))
            else:
                import asyncio

                await asyncio.to_thread(head_bucket, Bucket=str(bucket))
            return True
        except Exception:
            return False

    # Allow tests to inject after construction.
    @property
    def client(self) -> Any:
        return self._get_client()

    @client.setter
    def client(self, value: Any) -> None:
        self._provided_client = value
        self._client_cache = value

    @property
    def s3_client(self) -> Any:
        return self._get_client()

    @s3_client.setter
    def s3_client(self, value: Any) -> None:
        self._client_cache = value

    # ------------------------------------------------------------------ keys
    def _normalize_key(self, company_id: Any, key: Any) -> str:
        cid = _coerce_str(company_id)
        text = _as_text(key).strip()
        if text == '':
            raise AuthorizationError('object key is required and must be company-scoped')
        # Remove leading slashes.
        while text.startswith('/'):
            text = text[1:]
        if '/' in text:
            first = text.split('/', 1)[0]
            if first != cid:
                raise AuthorizationError(f'object key {text!r} is not scoped to company {cid!r}')
        else:
            text = f'{cid}/{text}'
        if not text.startswith(cid + '/'):
            raise AuthorizationError(f'object key {text!r} is not scoped to company {cid!r}')
        return text

    # Alias methods for key construction.
    def build_key(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        cid = _coerce_str(company_id)
        doc = _coerce_str(document_id)
        ver = _coerce_str(version_id)
        name = _as_text(filename).strip().lstrip('/')
        # prevent path traversal in filename
        name = name.split('/')[-1]
        if name == '':
            name = 'document'
        return f'{cid}/documents/{doc}/versions/{ver}/{name}'

    def make_key(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def object_key(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def generate_key(
        self, company_id: Any, document_id: Any, version_id: Any, filename: Any
    ) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def create_key(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def key_for(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def compose_key(self, company_id: Any, document_id: Any, version_id: Any, filename: Any) -> str:
        return self.build_key(company_id, document_id, version_id, filename)

    def validate_key(self, company_id: Any, key: Any) -> bool:
        try:
            self._normalize_key(company_id, key)
            return True
        except AuthorizationError:
            return False

    # ------------------------------------------------------------------ presign

    async def _generate_presigned_url(self, *args: Any, **kwargs: Any) -> Any:
        from ._s3_storage_presign import _generate_presigned_url as _m

        return await _m(self, *args, **kwargs)

    async def generate_presigned_upload_url(
        self, company_id: Any, key: Any = None, **kwargs: Any
    ) -> PresignedUpload:
        return cast(
            'PresignedUpload', await self._generate_presigned_url(company_id, key, **kwargs)
        )

    async def generate_presigned_download_url(
        self, company_id: Any, key: Any = None, **kwargs: Any
    ) -> PresignedUpload:
        expires_in = kwargs.pop('expires_in', None)
        if expires_in is None:
            expires_in = kwargs.pop('expiry', None)
        if expires_in is None:
            expires_in = kwargs.get('expires')
        default_expiry = getattr(self, 'default_download_expires_in', 300)
        ttl_keys = (
            'source_original_link_ttl_seconds',
            'ttl_seconds',
            'original_link_ttl_seconds',
            'download_ttl_seconds',
        )
        for ttl_key in ttl_keys:
            if ttl_key in kwargs and kwargs.get(ttl_key) is not None:
                default_expiry = kwargs.pop(ttl_key)
        return cast(
            'PresignedUpload',
            await self._generate_presigned_url(
                company_id,
                key,
                client_method='get_object',
                default_expiry=default_expiry,
                require_download_ttl=True,
                expires_in=expires_in,
                **kwargs,
            ),
        )

    async def get_object(self, company_id: Any, key: Any, **kwargs: Any) -> bytes:
        from ._s3_storage_get_object import _get_object as _m

        return await _m(self, company_id, key, **kwargs)  # type: ignore[no-any-return]

    async def head_object(self, company_id: Any, key: Any, **kwargs: Any) -> dict[str, object]:
        from ._s3_storage_head_object import head_object as _m

        return await _m(self, company_id, key, **kwargs)  # type: ignore[no-any-return]

    async def delete(self, company_id: Any, key: Any, **kwargs: Any) -> bool:
        scoped_key = self._normalize_key(company_id, key)
        bucket = _first(kwargs, 'bucket', 'bucket_name', 'documents_bucket', default=None)
        if bucket is None:
            bucket = self.bucket
        params = {'Bucket': bucket, 'Key': scoped_key}
        params.update(
            {
                k: v
                for k, v in kwargs.items()
                if k not in {'bucket', 'bucket_name', 'documents_bucket'}
            }
        )
        client = self._get_client()
        for method_name in ('delete_object', 'delete', 'remove', 'remove_object'):
            method = getattr(client, method_name, None)
            if callable(method):
                try:
                    res = method(**params)
                    res = await _await_value(res)
                    return True
                except Exception:  # noqa: S112
                    continue
        return False

    async def delete_object(self, company_id: Any, key: Any, **kwargs: Any) -> bool:
        return await self.delete(company_id, key, **kwargs)


_key_alias_names = [
    'make_key',
    'object_key',
    'generate_key',
    'create_key',
    'key_for',
    'compose_key',
]
for _ka in _key_alias_names:
    setattr(S3Storage, _ka, S3Storage.build_key)

# Method alias loops (compact binding)
_upload_url_aliases = [
    'create_presigned_upload_url',
    'presigned_upload_url',
    'get_presigned_upload_url',
    'generate_upload_url',
    'presigned_url',
    'upload_url',
    'get_presigned_url',
    'create_presigned_url',
    'get_upload_url',
]
for _a in _upload_url_aliases:
    setattr(S3Storage, _a, S3Storage.generate_presigned_upload_url)

_download_url_aliases = [
    'create_presigned_download_url',
    'presigned_download_url',
    'get_presigned_download_url',
    'download_url',
]
for _a in _download_url_aliases:
    setattr(S3Storage, _a, S3Storage.generate_presigned_download_url)

_head_aliases = ['head', 'stat', 'metadata']
for _a in _head_aliases:
    setattr(S3Storage, _a, S3Storage.head_object)

_get_aliases = ['get', 'download', 'fetch', 'read', 'read_object']
for _a in _get_aliases:
    setattr(S3Storage, _a, S3Storage.get_object)

_presign_download_variants = ['generate_presigned_download']
# handle specially if used


ObjectStorageAdapter = S3Storage
S3ObjectStorage = S3Storage
S3StorageAdapter = S3Storage
S3ObjectStorageAdapter = S3Storage
AwsS3Storage = S3Storage
AwsS3ObjectStorage = S3Storage
S3 = S3Storage
Storage = S3Storage

__all__ = [
    'S3',
    'AwsS3ObjectStorage',
    'AwsS3Storage',
    'ObjectStorageAdapter',
    'S3ObjectStorage',
    'S3ObjectStorageAdapter',
    'S3Storage',
    'S3StorageAdapter',
    'Storage',
]
