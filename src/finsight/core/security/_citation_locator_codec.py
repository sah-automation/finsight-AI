# ruff: noqa: BLE001, PLR0913, A002, TRY004

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from typing import Any

_PAYLOAD_KEYS = ('d', 'v', 'c', 't', 'p', 's', 'e', 'i')


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError('invalid base64url payload')
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


@dataclass(frozen=True)
class _CitationLocatorPayload:
    d: Any = None
    v: Any = None
    c: Any = None
    t: Any = None
    p: Any = None
    s: Any = None
    e: Any = None
    i: Any = None


class _CitationLocator(str):
    """A signed citation locator token (behaves as a string)."""

    def __new__(
        cls,
        token: str,
        payload: dict[str, Any] | None = None,
        *,
        secret_fingerprint: str | None = None,
    ) -> _CitationLocator:
        obj = super().__new__(cls, token)
        payload_value: dict[str, Any] | None = dict(payload) if payload is not None else None
        object.__setattr__(obj, '_payload', payload_value)
        object.__setattr__(obj, '_secret_fingerprint', secret_fingerprint)
        return obj

    @property
    def token(self) -> str:
        return str(self)

    @property
    def payload(self) -> dict[str, Any] | None:
        current = getattr(self, '_payload', None)
        if current is None:
            try:
                current = decode_citation_locator(self)
                self._payload = current
            except Exception:
                return None
        return current

    @property
    def claims(self) -> dict[str, Any] | None:
        return self.payload


def _normalize_claims(
    *,
    d: Any = None,
    v: Any = None,
    c: Any = None,
    t: Any = None,
    p: Any = None,
    s: Any = None,
    e: Any = None,
    i: Any = None,
    document_id: Any = None,
    document_version: Any = None,
    version: Any = None,
    version_id: Any = None,
    document_version_id: Any = None,
    chunk_id: Any = None,
    table_id: Any = None,
    type: Any = None,
    content_type: Any = None,
    page: Any = None,
    page_number: Any = None,
    char_start: Any = None,
    char_end: Any = None,
    start: Any = None,
    end: Any = None,
    start_char: Any = None,
    end_char: Any = None,
    locator_id: Any = None,
    issued_at: Any = None,
    expiry: Any = None,
    expires_at: Any = None,
    expires: Any = None,
    **kwargs: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _ = (expiry, expires_at, expires)
    resolved = {
        'd': _coalesce(
            d,
            document_id,
            kwargs.pop('document', None),
            kwargs.pop('doc_id', None),
            kwargs.pop('doc', None),
        ),
        'v': _coalesce(
            v,
            document_version,
            version,
            version_id,
            document_version_id,
            kwargs.pop('document_version_id', None),
        ),
        'c': _coalesce(c, chunk_id, kwargs.pop('chunk', None), kwargs.pop('chunk_id', None)),
        't': _coalesce(
            t, type, content_type, kwargs.pop('locator_type', None), kwargs.pop('table_type', None)
        ),
        'p': _coalesce(p, page, page_number, kwargs.pop('page_no', None)),
        's': _coalesce(
            s,
            char_start,
            start,
            start_char,
            kwargs.pop('charStart', None),
            kwargs.pop('startPosition', None),
        ),
        'e': _coalesce(
            e, char_end, end, end_char, kwargs.pop('charEnd', None), kwargs.pop('endPosition', None)
        ),
        'i': _coalesce(
            i, locator_id, issued_at, kwargs.pop('id', None), kwargs.pop('locatorId', None)
        ),
    }

    # Infer type/content marker when a table id is supplied without an explicit type.
    if resolved['t'] is None:
        if table_id is not None:
            if resolved['c'] is None:
                resolved['c'] = table_id
            resolved['t'] = 'table'
        elif resolved['c'] is not None:
            resolved['t'] = resolved['t'] if resolved['t'] is not None else 'chunk'

    if resolved['i'] is None:
        resolved['i'] = uuid.uuid4().hex

    # Only the canonical eight keys are retained; other keywords are ignored.
    for key in list(kwargs):
        if key in _PAYLOAD_KEYS:
            resolved[key] = _coalesce(resolved.get(key), kwargs.pop(key))
        else:
            kwargs.pop(key, None)

    payload = {key: resolved[key] for key in _PAYLOAD_KEYS}

    # Keep order of canonical keys.
    ordered = {key: payload[key] for key in _PAYLOAD_KEYS}
    return ordered, {}


def decode_citation_locator(token: Any) -> dict[str, Any]:
    if not isinstance(token, str):
        token = str(token)
    if '.' not in token:
        raise ValueError('invalid citation locator')
    payload_b64, _signature_b64 = token.split('.', 1)
    payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('invalid citation locator payload')
    return payload
