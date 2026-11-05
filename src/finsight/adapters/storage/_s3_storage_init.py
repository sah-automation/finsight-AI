# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._s3_storage_helpers import *


def _init_s3_storage(self: Any, *args: Any, **kwargs: Any) -> None:
    # Pull out likely constituents.
    self.config = _resolve_config(*args, **kwargs)
    self.storage_config = _storage_config(self.config)
    if 'storage_config' in kwargs and kwargs.get('storage_config') is not None:
        self.storage_config = kwargs.get('storage_config')
    if (
        'storage' in kwargs
        and isinstance(kwargs.get('storage'), (dict, object))
        and not isinstance(kwargs.get('storage'), (str, bytes))
    ):
        # Prefer explicit storage config object if provided.
        candidate = kwargs.get('storage')
        if hasattr(candidate, 'documents_bucket') or isinstance(candidate, dict):
            self.storage_config = candidate

    self._provided_client = _first(
        kwargs,
        'client',
        's3_client',
        'storage_client',
        'boto3_client',
        'aws_client',
        'object_storage_client',
        default=None,
    )
    for arg in args:
        if hasattr(arg, 'generate_presigned_url') or hasattr(arg, 'generate_presigned_post'):
            self._provided_client = arg
            break

    self._session = _resolve_session(*args, **kwargs)

    # Bucket selection.
    bucket = _first(
        kwargs,
        'bucket',
        'bucket_name',
        'documents_bucket',
        'documents_bucket_name',
        'storage_bucket',
        'bucket_documents',
        'bucket_name_documents',
        default=None,
    )
    if bucket is None and 'bucket' in kwargs:
        bucket = kwargs.get('bucket')
    if bucket is None and self.storage_config is not None:
        for attr in ('documents_bucket', 'bucket', 'bucket_name'):
            candidate = (
                getattr(self.storage_config, attr, None)
                if not isinstance(self.storage_config, dict)
                else self.storage_config.get(attr)
            )
            if candidate is not None:
                bucket = candidate
                break
    if bucket is None:
        bucket = 'documents'
    self.bucket = bucket

    # Region.
    region = _first(
        kwargs,
        'region',
        'aws_region',
        'region_name',
        default=None,
    )
    if region is None and self.storage_config is not None:
        region = (
            getattr(self.storage_config, 'region', None)
            if not isinstance(self.storage_config, dict)
            else self.storage_config.get('region')
        )
    if region is None:
        region = 'us-east-1'
    self.region = region

    # Endpoint.
    self.endpoint_url = _first(kwargs, 'endpoint_url', 'endpoint', default=None)

    # Document TTL (source_original_link_ttl_seconds) is read from config only.
    download_ttl = _first(
        kwargs,
        'source_original_link_ttl_seconds',
        'original_link_ttl_seconds',
        'download_ttl_seconds',
        'documents_source_original_link_ttl_seconds',
        default=None,
    )
    if download_ttl is None and self.config is not None:
        docs_cfg = getattr(self.config, 'documents', None)
        if docs_cfg is None and isinstance(self.config, dict):
            docs_cfg = self.config.get('documents')
        if isinstance(docs_cfg, dict):
            download_ttl = docs_cfg.get('source_original_link_ttl_seconds')
        else:
            download_ttl = getattr(docs_cfg, 'source_original_link_ttl_seconds', None)
    if download_ttl is None and self.storage_config is not None:
        for attr in ('source_original_link_ttl_seconds', 'original_link_ttl_seconds'):
            val = (
                getattr(self.storage_config, attr, None)
                if not isinstance(self.storage_config, dict)
                else self.storage_config.get(attr)
            )
            if val is not None:
                download_ttl = val
                break
    try:
        self.default_download_expires_in = int(download_ttl) if download_ttl is not None else 300
    except (TypeError, ValueError):
        self.default_download_expires_in = 300
    if self.default_download_expires_in < 1:
        self.default_download_expires_in = 300

    # Expiry default.
    expiry = _first(
        kwargs,
        'presigned_url_expiry_seconds',
        'expiry_seconds',
        'expires_in_seconds',
        'default_expires_in',
        'presigned_expiry',
        'url_expiry_seconds',
        default=None,
    )
    if expiry is None and self.storage_config is not None:
        expiry = (
            getattr(self.storage_config, 'presigned_url_expiry_seconds', None)
            if not isinstance(self.storage_config, dict)
            else self.storage_config.get('presigned_url_expiry_seconds')
        )
    try:
        self.default_expires_in = int(expiry) if expiry is not None else 900
    except (TypeError, ValueError):
        self.default_expires_in = 900
    if self.default_expires_in < 1:
        self.default_expires_in = 900

    # Encryption key mode (config switch).
    # Resolve a direct encryption-section object passed via constructor kwargs,
    # falling back to the accessor on the resolved config object.
    enc_cfg = None
    for _enc_key in ('encryption', 'encryption_config', 'encryption_section'):
        _cand = kwargs.get(_enc_key)
        if _cand is None:
            continue
        if isinstance(_cand, dict):
            enc_cfg = _cand.get('encryption', _cand.get('encryption_config', _cand))
        elif hasattr(_cand, 'encryption'):
            enc_cfg = _encryption_config(_cand)
            if enc_cfg is None:
                enc_cfg = _cand
        else:
            enc_cfg = _cand
        break
    if enc_cfg is None:
        enc_cfg = _encryption_config(self.config)
    key_mode = _first(
        kwargs,
        'key_mode',
        'encryption_key_mode',
        'encryption_mode',
        'key_mode',
        'mode',
        'sse',
        'server_side_encryption_mode',
        default=None,
    )
    if key_mode is None and enc_cfg is not None:
        for attr in ('key_mode', 'mode', 'server_side_encryption'):
            val = (
                getattr(enc_cfg, attr, None) if not isinstance(enc_cfg, dict) else enc_cfg.get(attr)
            )
            if val is not None:
                key_mode = val
                break
    if key_mode is None and self.storage_config is not None:
        for attr in ('key_mode', 'encryption_key_mode', 'encryption_mode'):
            val = (
                getattr(self.storage_config, attr, None)
                if not isinstance(self.storage_config, dict)
                else self.storage_config.get(attr)
            )
            if val is not None:
                key_mode = val
                break
    if key_mode is None:
        key_mode = 'aws_managed'
    key_mode = str(key_mode).strip().lower()
    if key_mode not in ('aws_managed', 'kms_customer'):
        raise ValueError(f'invalid encryption key_mode: {key_mode!r}')
    self.encryption_key_mode = key_mode
    self.key_mode = key_mode
    self.encryption_mode = key_mode
    self.encryption_config = enc_cfg

    # KMS / encryption.
    self.kms_key_id = _first(
        kwargs,
        'kms_key_id',
        'kms_key',
        'kms_key_alias',
        'key_id',
        'master_key_id',
        'sse_kms_key_id',
        'encryption_key_id',
        'encryption_key',
        default=None,
    )
    if self.kms_key_id is None and key_mode != 'aws_managed':
        # Allow alias from typed encryption config.
        if enc_cfg is not None:
            for attr in ('kms_key_alias', 'kms_key_id', 'key_id', 'key_alias', 'master_key_id'):
                val = (
                    getattr(enc_cfg, attr, None)
                    if not isinstance(enc_cfg, dict)
                    else enc_cfg.get(attr)
                )
                if val:
                    self.kms_key_id = val
                    break
    if self.kms_key_id is None:
        enc_cfg = _encryption_config(self.config)
        if enc_cfg is not None:
            for attr in ('kms_key_alias', 'kms_key_id', 'key_id', 'key_alias', 'master_key_id'):
                val = (
                    getattr(enc_cfg, attr, None)
                    if not isinstance(enc_cfg, dict)
                    else enc_cfg.get(attr)
                )
                if val:
                    self.kms_key_id = val
                    break
    if self.kms_key_id is None:
        storage_cfg = self.storage_config
        if storage_cfg is not None:
            for attr in ('kms_key_id', 'kms_key', 'sse_kms_key_id'):
                val = (
                    getattr(storage_cfg, attr, None)
                    if not isinstance(storage_cfg, dict)
                    else storage_cfg.get(attr)
                )
                if val:
                    self.kms_key_id = val
                    break

    # Keep loose extras for compatibility.
    for key, value in kwargs.items():
        if key not in self.__dict__:
            try:
                setattr(self, key, value)
            except Exception:
                pass

    if self.encryption_key_mode == 'kms_customer' and not self.kms_key_id:
        raise ValueError('kms_key_id is required when key_mode is kms_customer')
    if not hasattr(self, 'kms_key_id'):
        self.kms_key_id = None
    self._bucket_by_scope = {}
    self._client_cache = None
    if self._provided_client is not None:
        self._client_cache = self._provided_client


# ------------------------------------------------------------------ client
