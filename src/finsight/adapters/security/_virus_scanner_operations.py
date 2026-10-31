# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from finsight.core.errors import AuthorizationError, ExternalServiceError

from ._virus_scanner_helpers import (
    _as_bytes,
    _await_if_needed,
    _coerce_str,
    _first,
)


class _VirusScannerOperations:
    client: Any = None
    scan_func: Any = None
    object_storage: Any = None
    bucket: Any = None
    enabled: bool = True
    raise_on_failure: bool = False
    fail_closed: bool = True
    config: Any = None

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

        raise ExternalServiceError(
            'Unable to fetch scanned object; no object storage or get_object available'
        )
