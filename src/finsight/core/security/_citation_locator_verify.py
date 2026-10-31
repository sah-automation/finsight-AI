# ruff: noqa: BLE001, SIM102, PLR0911, PLR0912

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from ._citation_locator_codec import (
    _PAYLOAD_KEYS,
    _b64url_decode,
    _b64url_encode,
    _normalize_claims,
)


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


def verify_citation_locator(*args: Any, **kwargs: Any) -> Any:
    return _verify_citation_locator_impl(*args, **kwargs)


def _verify_citation_locator_impl(*args: Any, **kwargs: Any) -> bool:
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


def is_citation_locator_valid(*args: Any, **kwargs: Any) -> bool:
    return verify_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def validate_citation_locator(*args: Any, **kwargs: Any) -> bool:
    return verify_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def check_citation_locator(*args: Any, **kwargs: Any) -> bool:
    return verify_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]
