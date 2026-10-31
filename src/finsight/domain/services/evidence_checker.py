"""Evidence sufficiency checking for retrieval results (pure domain)."""

from __future__ import annotations

from typing import Any

from ._evidence_checker_math import (
    answer_has_evidence,
    is_citation_valid,
)
from ._evidence_checker_operations import _EvidenceCheckerOperations
from .evidence_result import EvidenceResult


class EvidenceChecker(_EvidenceCheckerOperations):
    """Decide whether retrieval produced enough evidence."""


def has_sufficient_evidence(*args: Any, **kwargs: Any) -> EvidenceResult:
    data = dict(kwargs)
    checker_kwargs: dict[str, object] = {}
    for key in (
        'min_score',
        'min_search_score',
        'min_chunks',
        'config',
        'settings',
        'evidence_min_score',
        'evidence_min_search_score',
        'evidence_min_chunks',
    ):
        if key in data:
            checker_kwargs[key] = data.pop(key)
    cfg_args = [a for a in args if hasattr(a, 'evidence_min_score') or hasattr(a, 'retrieval')]
    if cfg_args:
        checker_kwargs['config'] = cfg_args[0]
        args = tuple(a for a in args if a is not cfg_args[0])
    checker = EvidenceChecker(**checker_kwargs)
    return checker.check(*args, **data)  # type: ignore[no-any-return]


# Aliases
EvidenceService = EvidenceChecker
EvidenceGate = EvidenceChecker
EvidenceCheck = EvidenceChecker
__all__ = [
    'EvidenceCheck',
    'EvidenceChecker',
    'EvidenceGate',
    'EvidenceResult',
    'EvidenceService',
    'answer_has_evidence',
    'has_sufficient_evidence',
    'is_citation_valid',
]
