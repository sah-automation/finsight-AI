"""Alias module for evidence checker (compatibility)."""

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
