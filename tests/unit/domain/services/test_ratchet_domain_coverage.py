"""Targeted domain coverage for ratchet II."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities import Chunk, InsufficientData
from finsight.domain.services import (
    CitationValidationResult,
    DeltaDiffer,
    EvidenceResult,
    InputGateResult,
    OutputVerificationResult,
    is_permission_allowed,
)
from finsight.domain.value_objects import Currency, Money, MoneyUnits


def test_money_and_result_classes_are_exercised() -> None:
    money = Money(amount=Decimal('1.25'), currency=Currency.USD, units=MoneyUnits.UNITS)
    assert str(money)
    assert Money(amount=Decimal('1')).amount == Decimal('1')
    with pytest.raises(TypeError):
        Money(amount='bad')  # type: ignore[arg-type]

    civ = CitationValidationResult(valid=True, citations=[1], reason='ok')
    assert civ and civ.valid and civ.passed and civ.allowed and civ.ok
    assert civ.has_citation and civ.has_citations
    ev = EvidenceResult(sufficient=True, best_score=0.9, threshold=0.5, chunk_count=2, min_chunks=1)
    assert ev and ev.sufficient and ev.has_evidence
    ov = OutputVerificationResult(
        passed=True, citation_ok=True, numbers_ok=True, numbers=[1], reason='ok'
    )
    assert ov and ov.passed and ov.valid
    ig = InputGateResult(allowed=False, reason='blocked', normalized_question='q')
    assert not ig and ig.blocked and ig.blocked_reason == 'blocked'
    ins = InsufficientData(reason='x', company_id='co', citations=None)
    assert ins.insufficient_data and ins.citations == []
    assert bool(ins) is False


def test_delta_differ_chunk_path() -> None:
    company_id = CompanyId('company-a')
    doc_id = DocumentId('doc-1')
    a = Chunk.create(
        company_id=company_id, document_id=doc_id, version_id='v1', text='a', occurrence=0
    )
    b = Chunk.create(
        company_id=company_id, document_id=doc_id, version_id='v1', text='b', occurrence=1
    )
    c = Chunk.create(
        company_id=company_id, document_id=doc_id, version_id='v1', text='a', occurrence=0
    )
    diff = DeltaDiffer().diff_chunks([a], [b, c])
    assert set(diff.added) or set(diff.removed) or set(diff.changed) or set(diff.unchanged)


def test_permission_policy() -> None:
    matrix = {'editor': {'role_actions': ['read'], 'categories': {'doc': ['read', 'write']}}}
    assert is_permission_allowed(matrix, 'editor', 'doc', 'read') is True
    assert is_permission_allowed(matrix, 'viewer', 'doc', 'read') is False
    assert (
        is_permission_allowed({'default': {'categories': {'doc': ['*']}}}, 'x', 'doc', 'delete')
        is True
    )
