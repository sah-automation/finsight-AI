from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from ._citation_locator_codec import (
    _b64url_encode,
    _CitationLocator,
    _normalize_claims,
)


def mint_citation_locator(*args: Any, **kwargs: Any) -> Any:
    return _mint_citation_locator_impl(*args, **kwargs)


def _mint_citation_locator_impl(
    secret: Any = None,
    *args: object,
    secret_key: Any = None,
    signing_key: Any = None,
    key: Any = None,
    **claims: object,
) -> _CitationLocator:
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
    return _CitationLocator(token, payload)


def sign_citation_locator(*args: Any, **kwargs: Any) -> _CitationLocator:
    return mint_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def issue_citation_locator(*args: Any, **kwargs: Any) -> _CitationLocator:
    return mint_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def create_citation_locator(*args: Any, **kwargs: Any) -> _CitationLocator:
    return mint_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def generate_citation_locator(*args: Any, **kwargs: Any) -> _CitationLocator:
    return mint_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]


def make_citation_locator(*args: Any, **kwargs: Any) -> _CitationLocator:
    return mint_citation_locator(*args, **kwargs)  # type: ignore[no-any-return]
