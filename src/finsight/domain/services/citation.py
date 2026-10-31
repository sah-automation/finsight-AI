"""Alias module for citation checker (compatibility).

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from .citation_checker import (
    CitationCheck,
    CitationChecker,
    CitationValidationResult,
    CitationValidator,
    check_citation,
    validate_citation,
)

__all__ = [
    'CitationCheck',
    'CitationChecker',
    'CitationValidationResult',
    'CitationValidator',
    'check_citation',
    'validate_citation',
]
