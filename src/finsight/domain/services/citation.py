"""Alias module for citation checker (compatibility)."""

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
