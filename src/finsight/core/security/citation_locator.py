"""Signed, tamper-resistant citation locator tokens.

A locator is a compact base64url-encoded JSON payload joined by a dot to a
base64url-encoded HMAC-SHA256 over that payload. The dedicated source-viewer
signing secret never appears inside the token.
"""

from __future__ import annotations

from ._citation_locator_codec import (
    _CitationLocator as CitationLocator,
)
from ._citation_locator_codec import (
    _CitationLocatorPayload,
    decode_citation_locator,
)
from ._citation_locator_issue import (
    create_citation_locator,
    generate_citation_locator,
    issue_citation_locator,
    make_citation_locator,
    mint_citation_locator,
    sign_citation_locator,
)
from ._citation_locator_verify import (
    check_citation_locator,
    is_citation_locator_valid,
    validate_citation_locator,
    verify_citation_locator,
)

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
