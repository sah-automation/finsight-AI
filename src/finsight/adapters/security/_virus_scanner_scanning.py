# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from finsight.core.errors import ExternalServiceError
from finsight.domain.value_objects.virus_scan_result import VirusScanResult

from ._virus_scanner_helpers import (
    _as_bytes,
    _await_if_needed,
    _coerce_result,
    _coerce_str,
    _first,
)


class _VirusScannerScanning:
    _normalise_key: Any = None
    _resolve_scan_inputs: Any = None
    _fetch_object: Any = None
    client: Any = None
    scan_func: Any = None
    object_storage: Any = None
    bucket: Any = None
    enabled: bool = True
    raise_on_failure: bool = False
    fail_closed: bool = True
    config: Any = None

    async def _run_client_scan(
        self, company_id: Any, key: str, bucket: Any, data: bytes | None, **kwargs: Any
    ) -> VirusScanResult:
        client = self.client
        if client is None:
            return None  # type: ignore[return-value]

        method_names = (
            'scan_object',
            'scan_key',
            'scan_file',
            'scan_bytes',
            'scan_content',
            'scan_document',
            'scan',
            'check',
            'analyze',
            'inspect',
        )
        for name in method_names:
            method = getattr(client, name, None)
            if not callable(method):
                continue

            # Try a few call shapes.
            attempts = [
                lambda m=method: m(company_id, key, bucket=bucket, content=data, **kwargs),
                lambda m=method: m(
                    company_id=company_id, key=key, bucket=bucket, content=data, **kwargs
                ),
                lambda m=method: m(company_id, key, **kwargs),
                lambda m=method: m(key=key, company_id=company_id, **kwargs),
                lambda m=method: m(Bucket=bucket, Key=key, **kwargs),
                lambda m=method: m(bucket=bucket, key=key, **kwargs),
            ]
            for attempt in attempts:
                try:
                    res = attempt()  # type: ignore[no-untyped-call]
                    data_result = await _await_if_needed(res)
                    return _coerce_result(data_result)
                except TypeError:
                    continue
                except Exception as exc:
                    if self.raise_on_failure:
                        raise ExternalServiceError(f'Virus scan failed: {exc}') from exc
                    return VirusScanResult(clean=False, detail=_coerce_str(exc))
            # If all attempts TypeError, try next method.
        return None  # type: ignore[return-value]

    async def _run_scan_func(
        self, company_id: Any, key: str, bucket: Any, data: bytes | None, **kwargs: Any
    ) -> VirusScanResult:
        func = self.scan_func
        if not callable(func):
            return None  # type: ignore[return-value]
        attempts = [
            lambda f=func: f(company_id, key, bucket=bucket, content=data, **kwargs),
            lambda f=func: f(company_id=company_id, key=key, bucket=bucket, content=data, **kwargs),
            lambda f=func: f(company_id, key, data, **kwargs),
            lambda f=func: f(key, company_id, **kwargs),
            lambda f=func: f(data, **kwargs),
            lambda f=func: f(company_id, key, **kwargs),
        ]
        for attempt in attempts:
            try:
                res = attempt()  # type: ignore[no-untyped-call]
                data_result = await _await_if_needed(res)
                return _coerce_result(data_result)
            except TypeError:
                continue
            except Exception as exc:
                if self.raise_on_failure:
                    raise ExternalServiceError(f'Virus scan failed: {exc}') from exc
                return VirusScanResult(clean=False, detail=_coerce_str(exc))
        return None  # type: ignore[return-value]

    def _default_scan(self, data: bytes) -> VirusScanResult:
        if not data:
            return VirusScanResult(clean=True, detail='empty object')
        signatures = [
            b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE',
            b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*',
        ]
        haystack = data.lower()
        for signature in signatures:
            if signature.lower() in haystack:
                return VirusScanResult(clean=False, detail='EICAR test virus detected')
        # Keep additional known bad markers optional via attribute.
        extra = getattr(self, 'malicious_signatures', None) or getattr(
            self, 'virus_signatures', None
        )
        if isinstance(extra, (list, tuple, set)):
            for signature in extra:
                needle = signature.encode() if isinstance(signature, str) else bytes(signature)
                if needle.lower() in haystack:
                    return VirusScanResult(clean=False, detail=_coerce_str(signature))
        return VirusScanResult(clean=True, detail='clean')

    async def scan(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> VirusScanResult:
        company_id, key, content = self._resolve_scan_inputs(args, kwargs)
        bucket = _first(
            kwargs, 'bucket', 'bucket_name', 'storage_bucket', 'scan_bucket', default=None
        )
        if bucket is None:
            bucket = self.bucket

        normalized_key = (
            self._normalise_key(company_id, key)
            if (key is not None or content is not None)
            else f'{_coerce_str(company_id)}/scan'
        )

        if not bool(self.enabled):
            return VirusScanResult(clean=True, detail='virus scan disabled')

        data: bytes | None = _as_bytes(content) if content is not None else None

        # Scan function first (most explicit).
        if callable(self.scan_func):
            result = await self._run_scan_func(
                company_id,
                normalized_key,
                bucket,
                data,
                **{k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}},
            )
            if result is not None:
                return result

        # Client with scan methods.
        if self.client is not None:
            result = await self._run_client_scan(
                company_id,
                normalized_key,
                bucket,
                data,
                **{k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}},
            )
            if result is not None:
                return result

        # Fetch bytes then default scan.
        if data is None:
            try:
                data = await self._fetch_object(
                    company_id,
                    normalized_key,
                    bucket,
                    **{k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}},
                )
            except Exception as exc:
                if self.raise_on_failure:
                    raise
                return VirusScanResult(clean=False, detail=_coerce_str(exc))

        try:
            return self._default_scan(data or b'')
        except Exception as exc:
            if self.raise_on_failure:
                raise ExternalServiceError(f'Virus scan failed: {exc}') from exc
            return VirusScanResult(clean=False, detail=_coerce_str(exc))

    # Aliases required by port/compat.
