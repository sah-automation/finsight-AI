# ruff: noqa: PLE0605, F403
"""Virus scanning adapter implementing the VirusScanner port."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.virus_scanner import VirusScanner as VirusScannerPort
from finsight.domain.value_objects.virus_scan_result import VirusScanResult

from ._virus_scanner_helpers import *
from ._virus_scanner_helpers import (
    _first,
    _resolve_config,
    _resolve_enabled,
)
from ._virus_scanner_operations import _VirusScannerOperations
from ._virus_scanner_scanning import _VirusScannerScanning


class VirusScanner(_VirusScannerOperations, _VirusScannerScanning, VirusScannerPort):
    """Virus scanner adapter.

    Wraps an injected scanning backend / object-storage provider. When scanning
    is disabled, :meth:`scan` returns a clean result without contacting any
    backend, preserving the enabled/disabled switch path.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)
        self._raw_kwargs = dict(kwargs)

        # Client / backend discovery.
        provided_client = _first(
            kwargs,
            'client',
            'scanner_client',
            'scan_client',
            's3_client',
            'storage_client',
            'backend_client',
            'virus_scan_client',
            default=None,
        )
        for arg in args:
            if arg is None:
                continue
            if any(
                hasattr(arg, attr)
                for attr in (
                    'scan',
                    'scan_object',
                    'scan_key',
                    'get_object',
                    'head_object',
                    'generate_presigned_upload_url',
                )
            ):
                provided_client = arg
                break
        self.client = provided_client

        object_storage = _first(
            kwargs,
            'object_storage',
            'storage',
            'storage_adapter',
            'object_store',
            default=None,
        )
        for arg in args:
            if arg is None or arg is self.client:
                continue
            if hasattr(arg, 'get_object') or hasattr(arg, 'generate_presigned_upload_url'):
                object_storage = arg
                break
        self.object_storage = object_storage

        scan_func = _first(
            kwargs,
            'scan_func',
            'scanner',
            'scan_function',
            'backend',
            'engine',
            'provider',
            'scan_callable',
            default=None,
        )
        if scan_func is None:
            for key in ('scan_func', 'scanner', 'scan_function', 'backend', 'engine', 'provider'):
                candidate = kwargs.get(key)
                if callable(candidate):
                    scan_func = candidate
                    break
        # Also accept a bare callable passed positionally.
        for arg in args:
            if (
                arg is None
                or arg is self.client
                or arg is self.object_storage
                or isinstance(arg, (str, bytes, dict))
            ):
                continue
            if callable(arg) and not hasattr(arg, 'get_object'):
                scan_func = arg
                break
        self.scan_func = scan_func

        # Bucket resolution.
        bucket = _first(
            kwargs,
            'bucket',
            'bucket_name',
            'documents_bucket',
            'storage_bucket',
            'scan_bucket',
            default=None,
        )
        if bucket is None and self.config is not None:
            storage_cfg = getattr(self.config, 'storage', None)
            if storage_cfg is not None:
                bucket = getattr(storage_cfg, 'documents_bucket', None)
            if bucket is None and isinstance(self.config, dict):
                bucket = (self.config.get('storage') or {}).get('documents_bucket')
        if bucket is None:
            bucket = 'documents'
        self.bucket = bucket

        # Enabled / disabled.
        self.enabled = _resolve_enabled(self.config, kwargs)
        self.virus_scan_enabled = self.enabled
        self.scan_enabled = self.enabled
        self.virus_scanning_enabled = self.enabled

        # Failure behaviour.
        self.raise_on_failure = _first(kwargs, 'raise_on_failure', 'fail_fast', default=False)
        try:
            self.raise_on_failure = (
                bool(self.raise_on_failure) if self.raise_on_failure is not None else False
            )
        except Exception:
            self.raise_on_failure = False

        self.fail_closed = _first(kwargs, 'fail_closed', 'fail_closed_on_error', default=True)
        try:
            self.fail_closed = bool(self.fail_closed) if self.fail_closed is not None else True
        except Exception:
            self.fail_closed = True

        # Keep loose extras.
        for key, value in kwargs.items():
            if key not in self.__dict__:
                try:
                    setattr(self, key, value)
                except Exception:
                    pass

    # ------------------------------------------------------------------ helpers

    async def scan_object(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def scan_key(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def scan_file(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def scan_bytes(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def scan_content(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def scan_document(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def check(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def analyze(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)  # type: ignore[no-any-return]

    async def is_clean(self, *args: Any, **kwargs: Any) -> bool:
        result = await self.scan(*args, **kwargs)
        return bool(result.clean)

    async def is_infected(self, *args: Any, **kwargs: Any) -> bool:
        result = await self.scan(*args, **kwargs)
        return bool(result.infected)

    # Sync/async mixing is intentionally avoided: callers await scan() directly.


_virus_aliases = [
    'VirusScannerAdapter',
    'AwsVirusScanner',
    'AWSVirusScanner',
    'ClamAVScanner',
    'ClamAvScanner',
    'MalwareScanner',
    'SecurityScanner',
    'Scanner',
    'DefaultVirusScanner',
    'VirusScanAdapter',
    'VirusScannerImpl',
]
for _va in _virus_aliases:
    globals()[_va] = VirusScanner
VirusScannerAdapter = VirusScanner
__all__ = sorted([*_virus_aliases, 'VirusScanner', 'VirusScannerAdapter'])
