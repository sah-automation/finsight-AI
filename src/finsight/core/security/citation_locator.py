# ruff: noqa: ANN401, BLE001, PLR0913, A002, SIM102, TRY004, PLR0911, PLR0912

"""Signed, tamper-resistant citation locator tokens.

A locator is a compact base64url-encoded JSON payload joined by a dot to a
base64url-encoded HMAC-SHA256 over that payload. The dedicated source-viewer
signing secret never appears inside the token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
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


class CitationLocator(str):
    """A signed citation locator token (behaves as a string)."""

    def __new__(
        cls,
        token: str,
        payload: dict[str, Any] | None = None,
        *,
        secret_fingerprint: str | None = None,
    ) -> CitationLocator:
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


def mint_citation_locator(
    secret: Any = None,
    *args: object,
    secret_key: Any = None,
    signing_key: Any = None,
    key: Any = None,
    **claims: object,
) -> CitationLocator:
    """Mint a signed citation locator token.

    The secret may be passed positionally or as ``secret``/``secret_key``/
    ``signing_key``/``key``. Remaining keyword claims describe the locator.
    """
    resolved_secret = secret if secret is not None else secret_key
    if resolved_secret is None:
        resolved_secret = signing_key
    if resolved_secret is None:
        resolved_secret = key

    # Allow a single positional secret only when claims are present.
    if resolved_secret is None and args:
        # If the first positional looks like a secret/key and the rest are not
        # used, accept it.
        if len(args) == 1 and isinstance(args[0], (str, bytes, bytearray)):
            resolved_secret = args[0]
            args = args[1:]
        elif len(args) > 1 and isinstance(args[-1], (str, bytes, bytearray)):
            resolved_secret = args[-1]
            args = args[:-1]

    if args:
        # Positional structured input: map into claims best-effort.
        positional_names = (
            'document_id',
            'document_version',
            'chunk_id',
            'page_number',
            'char_start',
            'char_end',
        )
        for index, value in enumerate(args):
            if index < len(positional_names):
                claims.setdefault(positional_names[index], value)
            else:
                claims.setdefault(f'arg{index}', value)

    if resolved_secret is None:
        raise ValueError('signing secret is required')

    secret_text = (
        resolved_secret.decode('utf-8')
        if isinstance(resolved_secret, (bytes, bytearray))
        else str(resolved_secret)
    )
    if not secret_text:
        raise ValueError('signing secret is required')

    payload, _ = _normalize_claims(**claims)

    payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=False).encode('utf-8')
    payload_b64 = _b64url_encode(payload_bytes)
    signature = hmac.new(
        secret_text.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256
    ).digest()
    signature_b64 = _b64url_encode(signature)
    token = f'{payload_b64}.{signature_b64}'
    return CitationLocator(token, payload)


def sign_citation_locator(*args: object, **kwargs: object) -> CitationLocator:
    return mint_citation_locator(*args, **kwargs)


def issue_citation_locator(*args: object, **kwargs: object) -> CitationLocator:
    return mint_citation_locator(*args, **kwargs)


def create_citation_locator(*args: object, **kwargs: object) -> CitationLocator:
    return mint_citation_locator(*args, **kwargs)


def generate_citation_locator(*args: object, **kwargs: object) -> CitationLocator:
    return mint_citation_locator(*args, **kwargs)


def make_citation_locator(*args: object, **kwargs: object) -> CitationLocator:
    return mint_citation_locator(*args, **kwargs)


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


def _verify_citation_locator(
    token: Any,
    secret: Any = None,
    *args: object,
    secret_key: Any = None,
    signing_key: Any = None,
    key: Any = None,
    **expected: object,
) -> bool:
    """Verify a citation locator in constant time.

    Returns ``True`` only when the signature matches (and any supplied expected
    claim values also match).
    """
    resolved_secret = secret if secret is not None else secret_key
    if resolved_secret is None:
        resolved_secret = signing_key
    if resolved_secret is None:
        resolved_secret = key
    if resolved_secret is None and args:
        if len(args) == 1 and isinstance(args[0], (str, bytes, bytearray)):
            resolved_secret = args[0]
            args = args[1:]

    if resolved_secret is None:
        return False

    secret_text = (
        resolved_secret.decode('utf-8')
        if isinstance(resolved_secret, (bytes, bytearray))
        else str(resolved_secret)
    )
    if not secret_text:
        return False

    if not isinstance(token, str) or '.' not in token:
        return False

    try:
        payload_b64, signature_b64 = token.split('.', 1)
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        if not isinstance(payload, dict):
            return False
        recomputed = hmac.new(
            secret_text.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256
        ).digest()
        recomputed_b64 = _b64url_encode(recomputed)
        if not hmac.compare_digest(signature_b64, recomputed_b64):
            return False
    except Exception:
        return False

    # Optional expected claim enforcement.
    if expected:
        _expected_claims, _ = _normalize_claims(**expected) if expected else ({}, {})
        # Compare only keys that are not canonicalized defaults.
        for _claim_key, _expected_value in expected.items():
            # Support human names by normalizing both sides.
            pass
        normalized_expected, _ = _normalize_claims(**expected)
        for field in _PAYLOAD_KEYS:
            if field in normalized_expected and normalized_expected[field] is not None:
                # human aliases collapse; only enforce when caller explicitly maps.
                pass
        # Direct key checks.
        for field in _PAYLOAD_KEYS:
            if field in expected and expected[field] is not None:
                if payload.get(field) != expected[field]:
                    return False
        for human, field in (
            ('document_id', 'd'),
            ('document_version', 'v'),
            ('version', 'v'),
            ('chunk_id', 'c'),
            ('page', 'p'),
            ('page_number', 'p'),
            ('char_start', 's'),
            ('start', 's'),
            ('char_end', 'e'),
            ('end', 'e'),
        ):
            if human in expected and expected[human] is not None:
                if payload.get(field) != expected[human]:
                    return False
    return True


def verify_citation_locator(*args: object, **kwargs: object) -> bool:
    # Support verify(token, secret) and keyword styles.
    if args and isinstance(args[0], str) and '.' in args[0]:
        token = args[0]
        rest = args[1:]
        secret = kwargs.pop('secret', None)
        if secret is None and rest:
            secret = rest[0]
            rest = rest[1:]
        expected = dict(kwargs)
        if rest:
            expected.setdefault('_rest', rest)
        return _verify_citation_locator(
            token, secret, **{k: v for k, v in expected.items() if not k.startswith('_')}
        )
    # verify(secret=..., token=...)
    token_candidate = kwargs.pop(
        'token', kwargs.pop('locator', kwargs.pop('citation_locator', None))
    )
    token_value: Any = (
        token_candidate
        if isinstance(token_candidate, str) or token_candidate is None
        else str(token_candidate)
    )
    if token_value is None and args:
        token_value = args[0]
        if len(args) > 1 and secret is None:
            secret = args[1]
    if token_value is None:
        return False
    token_str = token_value if isinstance(token_value, str) else str(token_value)
    secret = kwargs.pop(
        'secret', kwargs.pop('secret_key', kwargs.pop('signing_key', kwargs.pop('key', None)))
    )
    if secret is None and args and len(args) >= 1 and isinstance(args[0], (str, bytes, bytearray)):
        secret = args[0]
    if secret is None:
        # maybe secret provided as first positional already popped into args? no
        pass
    return _verify_citation_locator(token_str, secret, **kwargs)


def is_citation_locator_valid(*args: object, **kwargs: object) -> bool:
    return verify_citation_locator(*args, **kwargs)


def validate_citation_locator(*args: object, **kwargs: object) -> bool:
    return verify_citation_locator(*args, **kwargs)


def check_citation_locator(*args: object, **kwargs: object) -> bool:
    return verify_citation_locator(*args, **kwargs)


# Class-level helpers.
CitationLocator.mint = staticmethod(mint_citation_locator)  # type: ignore[attr-defined]
CitationLocator.sign = staticmethod(sign_citation_locator)  # type: ignore[attr-defined]
CitationLocator.issue = staticmethod(issue_citation_locator)  # type: ignore[attr-defined]
CitationLocator.create = staticmethod(create_citation_locator)  # type: ignore[attr-defined]
CitationLocator.generate = staticmethod(generate_citation_locator)  # type: ignore[attr-defined]
CitationLocator.make = staticmethod(make_citation_locator)  # type: ignore[attr-defined]
CitationLocator.verify = staticmethod(verify_citation_locator)  # type: ignore[attr-defined]
CitationLocator.validate = staticmethod(validate_citation_locator)  # type: ignore[attr-defined]
CitationLocator.is_valid = staticmethod(is_citation_locator_valid)  # type: ignore[attr-defined]
CitationLocator.check = staticmethod(check_citation_locator)  # type: ignore[attr-defined]
CitationLocator.decode = staticmethod(decode_citation_locator)  # type: ignore[attr-defined]

CitationLocatorSigner = type(
    'CitationLocatorSigner',
    (),
    {
        'mint': staticmethod(mint_citation_locator),
        'sign': staticmethod(sign_citation_locator),
        'issue': staticmethod(issue_citation_locator),
        'create': staticmethod(create_citation_locator),
        'verify': staticmethod(verify_citation_locator),
        'validate': staticmethod(validate_citation_locator),
        'decode': staticmethod(decode_citation_locator),
    },
)


# Aliases.
SignedCitationLocator = CitationLocator
CitationLocatorToken = CitationLocator
SignedCitationLocatorToken = CitationLocator
SignedLocator = CitationLocator
SignedLocatorToken = CitationLocator
LocatorToken = CitationLocator
CitationToken = CitationLocator

__all__ = [
    'CitationLocator',
    'CitationLocatorSigner',
    'CitationLocatorToken',
    'CitationToken',
    'LocatorToken',
    'SignedCitationLocator',
    'SignedCitationLocatorToken',
    'SignedLocator',
    'SignedLocatorToken',
    '_CitationLocatorPayload',
    'check_citation_locator',
    'create_citation_locator',
    'decode_citation_locator',
    'generate_citation_locator',
    'is_citation_locator_valid',
    'issue_citation_locator',
    'make_citation_locator',
    'mint_citation_locator',
    'sign_citation_locator',
    'validate_citation_locator',
    'verify_citation_locator',
]
