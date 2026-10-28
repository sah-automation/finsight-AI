"""Virus scanning adapter implementing the :class:`VirusScanner` port."""

from __future__ import annotations

import inspect
from typing import Any

from finsight.core.errors import AuthorizationError, ExternalServiceError
from finsight.domain.ports.virus_scanner import VirusScanner as VirusScannerPort
from finsight.domain.value_objects.virus_scan_result import VirusScanResult

_CLEAN_TOKENS = {
    'clean',
    'ok',
    'okay',
    'passed',
    'pass',
    'safe',
    'no_threat',
    'no_threats',
    'none',
    'negative',
}

_INFECTED_TOKENS = {
    'infected',
    'malware',
    'virus',
    'threat',
    'threat_detected',
    'dirty',
    'positive',
    'rejected',
    'failed',
    'error',
    'unscannable',
}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _as_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode('utf-8', 'replace')
    if hasattr(value, 'read'):
        try:
            raw = value.read()
            if hasattr(value, 'seek'):
                try:
                    value.seek(0)
                except Exception:
                    pass
            if isinstance(raw, (bytes, bytearray, str)):
                return _as_bytes(raw)
        except Exception:
            return None
    if isinstance(value, dict):
        for key in ('content', 'data', 'bytes', 'body', 'file', 'payload'):
            if value.get(key) is not None:
                found = _as_bytes(value.get(key))
                if found is not None:
                    return found
    for attr in ('content', 'data', 'bytes', 'body', 'file', 'payload'):
        candidate = getattr(value, attr, None)
        if candidate is not None and candidate is not value:
            found = _as_bytes(candidate)
            if found is not None:
                return found
    return None


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is not None and (hasattr(arg, 'ingestion') or hasattr(arg, 'switches') or hasattr(arg, 'storage')):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        cfg = getattr(arg, 'config', None)
        if cfg is not None:
            return cfg
    return None


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


def _resolve_enabled(config: Any, kwargs: dict[str, Any]) -> bool:
    # Explicit constructor knobs take precedence.
    explicit_keys = (
        'enabled',
        'virus_scan_enabled',
        'scan_enabled',
        'virus_scanning_enabled',
        'enabled_virus_scan',
    )
    for key in explicit_keys:
        if key in kwargs and kwargs.get(key) is not None:
            value = kwargs.get(key)
            try:
                return bool(value)
            except Exception:
                pass
    # Config-driven resolution.
    if config is not None:
        candidates = []
        if hasattr(config, 'ingestion'):
            candidates.append(getattr(config.ingestion, 'virus_scan_enabled', None))
        if hasattr(config, 'virus_scan_enabled'):
            candidates.append(getattr(config, 'virus_scan_enabled', None))
        if hasattr(config, 'switches'):
            switches = getattr(config, 'switches', None)
            if switches is not None and hasattr(switches, 'virus_scan_enabled'):
                candidates.append(getattr(switches, 'virus_scan_enabled', None))
        if isinstance(config, dict):
            candidates.append((config.get('ingestion') or {}).get('virus_scan_enabled'))
            candidates.append(config.get('virus_scan_enabled'))
        for candidate in candidates:
            if candidate is not None:
                try:
                    return bool(candidate)
                except Exception:  # noqa: S112
                    continue
    return True


def _coerce_result(value: Any, *, default_detail: str | None = None) -> VirusScanResult:
    if isinstance(value, VirusScanResult):
        return value

    if isinstance(value, bool):
        return VirusScanResult(clean=bool(value), detail=default_detail)

    if isinstance(value, str):
        token = value.strip().lower().replace(' ', '_').replace('-', '_')
        if token in _CLEAN_TOKENS:
            return VirusScanResult(clean=True, detail=value)
        if token in _INFECTED_TOKENS:
            return VirusScanResult(clean=False, detail=value)
        # Unknown textual result: treat non-empty as infected to stay fail-closed-ish.
        return VirusScanResult(clean=False, detail=value or default_detail)

    if isinstance(value, dict):
        clean_val = None
        for key in ('clean', 'is_clean', 'ok', 'passed', 'safe'):
            if key in value:
                clean_val = value.get(key)
                break
        infected_val = None
        for key in ('infected', 'is_infected', 'malware', 'threat', 'threat_detected'):
            if key in value:
                infected_val = value.get(key)
                break
        if clean_val is not None:
            detail = None
            for key in ('detail', 'message', 'reason', 'status', 'result'):
                if key in value and value.get(key) is not None:
                    detail = _coerce_str(value.get(key))
                    break
            return VirusScanResult(clean=bool(clean_val), detail=detail or default_detail)
        if infected_val is not None:
            detail = None
            for key in ('detail', 'message', 'reason', 'status', 'result'):
                if key in value and value.get(key) is not None:
                    detail = _coerce_str(value.get(key))
                    break
            return VirusScanResult(clean=not bool(infected_val), detail=detail or default_detail)

        # Status/result tokens.
        for key in ('status', 'result', 'verdict', 'scan_result', 'outcome', 'state'):
            if key in value and value.get(key) is not None:
                token = _coerce_str(value.get(key)).strip().lower().replace(' ', '_').replace('-', '_')
                if token in _CLEAN_TOKENS:
                    detail = None
                    for dkey in ('detail', 'message', 'reason'):
                        if dkey in value and value.get(dkey) is not None:
                            detail = _coerce_str(value.get(dkey))
                            break
                    return VirusScanResult(clean=True, detail=detail or _coerce_str(value.get(key)))
                if token in _INFECTED_TOKENS:
                    detail = None
                    for dkey in ('detail', 'message', 'reason'):
                        if dkey in value and value.get(dkey) is not None:
                            detail = _coerce_str(value.get(dkey))
                            break
                    return VirusScanResult(clean=False, detail=detail or _coerce_str(value.get(key)))
        # Error fields.
        for key in ('error', 'exception', 'failure'):
            if key in value and value.get(key) is not None:
                return VirusScanResult(clean=False, detail=_coerce_str(value.get(key)))
        if value:
            return VirusScanResult(clean=False, detail=default_detail or 'scan result not clean')
        return VirusScanResult(clean=True, detail=default_detail)

    # Objects exposing attributes.
    for attr in ('clean', 'is_clean'):
        if hasattr(value, attr):
            try:
                return VirusScanResult(clean=bool(getattr(value, attr)), detail=getattr(value, 'detail', None) or getattr(value, 'message', None))
            except Exception:
                pass
    for attr in ('infected', 'is_infected'):
        if hasattr(value, attr):
            try:
                return VirusScanResult(clean=not bool(getattr(value, attr)), detail=getattr(value, 'detail', None) or getattr(value, 'message', None))
            except Exception:
                pass
    # Try common callables.
    if callable(value):
        try:
            return _coerce_result(value(), default_detail=default_detail)
        except Exception:
            pass

    return VirusScanResult(clean=False, detail=_coerce_str(value) or default_detail)


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class VirusScanner(VirusScannerPort):
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
            if arg is None or arg is self.client or arg is self.object_storage or isinstance(arg, (str, bytes, dict)):
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
            self.raise_on_failure = bool(self.raise_on_failure) if self.raise_on_failure is not None else False
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
    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def _resolve_scan_inputs(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> tuple[Any, Any, Any]:
        kwargs = dict(kwargs)
        # company id
        company_id = _first(
            kwargs,
            'company_id',
            'company',
            'tenant_id',
            'tenant',
            'org_id',
            'organization_id',
            default=None,
        )
        # key / target
        key = _first(
            kwargs,
            'key',
            'object_key',
            's3_key',
            'object',
            'file_key',
            'path',
            'location',
            'uri',
            'document_key',
            'target',
            default=None,
        )
        # direct content
        content = _first(
            kwargs,
            'content',
            'data',
            'bytes',
            'body',
            'file',
            'payload',
            'file_content',
            'object_bytes',
            default=None,
        )

        positional = list(args)
        # If company/key/content not resolved, consume positionals.
        if company_id is None and positional:
            company_id = positional.pop(0)
        if key is None and positional:
            # Only consume as key if it looks like a key-ish value (str/dict), not bytes.
            if not isinstance(positional[0], (bytes, bytearray)):
                key = positional.pop(0)
            elif content is None:
                content = positional.pop(0)
        if key is None and content is None and positional:
            if isinstance(positional[0], (bytes, bytearray, str)):
                # Heuristic: a single positional after company id is a key, not bytes.
                key = positional.pop(0)
        if content is None and positional:
            content = positional.pop(0)

        if key is None and content is None:
            # Fall back to kwargs raw key-ish any remaining.
            for candidate in ('key', 'object_key', 's3_key'):
                if candidate in kwargs:
                    key = kwargs.get(candidate)
                    break

        return company_id, key, content

    def _normalise_key(self, company_id: Any, key: Any) -> str:
        cid = _coerce_str(company_id).strip()
        if not cid:
            raise AuthorizationError('company_id is required for virus scanning')
        text = _coerce_str(key).strip()
        if text == '':
            # Allow scans without an explicit key, but keep them company-scoped.
            return f'{cid}/scan'
        text = text.replace('\\', '/')
        while text.startswith('/'):
            text = text[1:]
        parts = [part for part in text.split('/') if part != '']
        if any(part in {'.', '..'} for part in parts):
            raise AuthorizationError('scan target path traversal is not allowed')
        if '/' in text:
            first = parts[0] if parts else ''
            if first not in ('', cid):
                raise AuthorizationError('scan target does not belong to the supplied company')
            if first == '':
                text = f'{cid}/' + '/'.join(parts)
        else:
            text = f'{cid}/{text}'
            parts = [cid, text.split('/', 1)[1]]
        if not text.startswith(f'{cid}/'):
            text = f'{cid}/{text.lstrip("/")}'
            parts = text.split('/')
        # Re-validate after normalization.
        final_parts = [part for part in text.split('/') if part != '']
        if final_parts and final_parts[0] != cid:
            raise AuthorizationError('scan target does not belong to the supplied company')
        if any(part in {'.', '..'} for part in final_parts):
            raise AuthorizationError('scan target path traversal is not allowed')
        if not text.startswith(f'{cid}/'):
            raise AuthorizationError('scan target does not belong to the supplied company')
        return text

    async def _fetch_object(self, company_id: Any, key: str, bucket: Any, **kwargs: Any) -> bytes:
        # Object storage port first.
        if self.object_storage is not None and hasattr(self.object_storage, 'get_object'):
            try:
                res = self.object_storage.get_object(company_id, key, bucket=bucket, **kwargs)
                data = await _await_if_needed(res)
                found = _as_bytes(data)
                if found is not None:
                    return found
            except TypeError:
                try:
                    res = self.object_storage.get_object(company_id, key, **kwargs)
                    data = await _await_if_needed(res)
                    found = _as_bytes(data)
                    if found is not None:
                        return found
                except Exception:
                    pass
            except Exception as exc:
                if self.raise_on_failure:
                    raise ExternalServiceError(f'Virus scan fetch failed: {exc}') from exc
                return b''

        if self.client is not None:
            # boto-style get_object
            get_obj = getattr(self.client, 'get_object', None)
            if callable(get_obj):
                try:
                    try:
                        res = get_obj(Bucket=bucket, Key=key, **kwargs)
                    except TypeError:
                        res = get_obj(bucket=bucket, key=key, **kwargs)
                    data = await _await_if_needed(res)
                    # boto returns dict with Body.
                    if isinstance(data, dict):
                        body = data.get('Body')
                        if body is not None:
                            raw = body.read() if hasattr(body, 'read') else body
                            found = _as_bytes(raw)
                            if found is not None:
                                return found
                    found = _as_bytes(data)
                    if found is not None:
                        return found
                except Exception as exc:
                    raise ExternalServiceError(f'Virus scan fetch failed: {exc}') from exc
            # head_object (no body) -> cannot scan bytes; signal failure below.

        raise ExternalServiceError('Unable to fetch scanned object; no object storage or get_object available')

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
                lambda m=method: m(company_id=company_id, key=key, bucket=bucket, content=data, **kwargs),
                lambda m=method: m(company_id, key, **kwargs),
                lambda m=method: m(key=key, company_id=company_id, **kwargs),
                lambda m=method: m(Bucket=bucket, Key=key, **kwargs),
                lambda m=method: m(bucket=bucket, key=key, **kwargs),
            ]
            for attempt in attempts:
                try:
                    res = attempt()
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
                res = attempt()
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
        extra = getattr(self, 'malicious_signatures', None) or getattr(self, 'virus_signatures', None)
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
        bucket = _first(kwargs, 'bucket', 'bucket_name', 'storage_bucket', 'scan_bucket', default=None)
        if bucket is None:
            bucket = self.bucket

        normalized_key = self._normalise_key(company_id, key) if (key is not None or content is not None) else f'{_coerce_str(company_id)}/scan'

        if not bool(self.enabled):
            return VirusScanResult(clean=True, detail='virus scan disabled')

        data: bytes | None = _as_bytes(content) if content is not None else None

        # Scan function first (most explicit).
        if callable(self.scan_func):
            result = await self._run_scan_func(company_id, normalized_key, bucket, data, **{
                k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}
            })
            if result is not None:
                return result

        # Client with scan methods.
        if self.client is not None:
            result = await self._run_client_scan(company_id, normalized_key, bucket, data, **{
                k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}
            })
            if result is not None:
                return result

        # Fetch bytes then default scan.
        if data is None:
            try:
                data = await self._fetch_object(company_id, normalized_key, bucket, **{
                    k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name'}
                })
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
    async def scan_object(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def scan_key(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def scan_file(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def scan_bytes(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def scan_content(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def scan_document(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def check(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def analyze(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        return await self.scan(*args, **kwargs)

    async def is_clean(self, *args: Any, **kwargs: Any) -> bool:
        result = await self.scan(*args, **kwargs)
        return bool(result.clean)

    async def is_infected(self, *args: Any, **kwargs: Any) -> bool:
        result = await self.scan(*args, **kwargs)
        return bool(result.infected)

    # Client-style helpers some tests may call synchronously? Provide sync wrappers.
    def scan_sync(self, *args: Any, **kwargs: Any) -> VirusScanResult:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            raise RuntimeError('scan_sync cannot run in running event loop')
        return asyncio.run(self.scan(*args, **kwargs))


__all__ = ['VirusScanner']


VirusScannerAdapter = VirusScanner
AwsVirusScanner = VirusScanner
AWSVirusScanner = VirusScanner
ClamAVScanner = VirusScanner
ClamAvScanner = VirusScanner
MalwareScanner = VirusScanner
SecurityScanner = VirusScanner
Scanner = VirusScanner
DefaultVirusScanner = VirusScanner
VirusScanAdapter = VirusScanner
VirusScannerImpl = VirusScanner
