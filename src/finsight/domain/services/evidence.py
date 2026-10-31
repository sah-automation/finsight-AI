"""Alias module for evidence checker (compatibility).

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from .evidence_checker import (
    EvidenceCheck,
    EvidenceChecker,
    EvidenceGate,
    EvidenceResult,
    EvidenceService,
    answer_has_evidence,
    has_sufficient_evidence,
    is_citation_valid,
)

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
