"""Security tests for tenant-scoped answer cache keys."""

from __future__ import annotations

import pytest

from finsight.core.types import DocumentCategory, Role
from finsight.domain.services.cache_key import build_answer_cache_key

pytestmark = pytest.mark.security

SHA256_HEX_LENGTH = 64


class DummyContext:
    def __init__(
        self,
        company_id: str = 'company-a',
        role: Role = Role.CORPORATE_FINANCE_PLANNERS,
        access_scope: list[DocumentCategory] | None = None,
    ) -> None:
        self.company_id = company_id
        self.role = role
        self.access_scope = (
            access_scope
            if access_scope is not None
            else [
                DocumentCategory.INVOICE,
                DocumentCategory.BANK_STATEMENT,
            ]
        )


def _context(
    company_id: str = 'company-a',
    role: Role = Role.CORPORATE_FINANCE_PLANNERS,
    access_scope: list[DocumentCategory] | None = None,
) -> object:
    return DummyContext(company_id=company_id, role=role, access_scope=access_scope)


class TestAnswerCacheKey:
    """The cache key must include every dimension that changes the answer."""

    def test_key_is_deterministic(self) -> None:
        first = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')
        second = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')

        assert first == second

    def test_company_id_changes_the_key(self) -> None:
        first = build_answer_cache_key(_context('company-a'), 'What is revenue?', 'stamp-1')
        second = build_answer_cache_key(_context('company-b'), 'What is revenue?', 'stamp-1')

        assert first != second

    def test_role_changes_the_key(self) -> None:
        first = build_answer_cache_key(
            _context(role=Role.CORPORATE_FINANCE_PLANNERS), 'What is revenue?', 'stamp-1'
        )
        second = build_answer_cache_key(
            _context(role=Role.AUDIT_COMPLIANCE), 'What is revenue?', 'stamp-1'
        )

        assert first != second

    def test_access_scope_changes_the_key(self) -> None:
        first = build_answer_cache_key(
            _context(access_scope=[DocumentCategory.BUDGET]), 'What is revenue?', 'stamp-1'
        )
        second = build_answer_cache_key(
            _context(access_scope=[DocumentCategory.BUDGET, DocumentCategory.FINANCIAL_STATEMENT]),
            'What is revenue?',
            'stamp-1',
        )

        assert first != second

    def test_access_scope_order_does_not_matter(self) -> None:
        first = build_answer_cache_key(
            _context(access_scope=[DocumentCategory.BUDGET, DocumentCategory.FINANCIAL_STATEMENT]),
            'What is revenue?',
            'stamp-1',
        )
        second = build_answer_cache_key(
            _context(access_scope=[DocumentCategory.FINANCIAL_STATEMENT, DocumentCategory.BUDGET]),
            'What is revenue?',
            'stamp-1',
        )

        assert first == second

    def test_question_changes_the_key(self) -> None:
        first = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')
        second = build_answer_cache_key(_context(), 'What is profit?', 'stamp-1')

        assert first != second

    def test_document_stamp_changes_the_key(self) -> None:
        first = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')
        second = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-2')

        assert first != second

    def test_question_whitespace_is_normalised(self) -> None:
        first = build_answer_cache_key(_context(), '  What   is revenue? ', 'stamp-1')
        second = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')

        assert first == second

    def test_key_is_a_sha256_hex_digest(self) -> None:
        key = build_answer_cache_key(_context(), 'What is revenue?', 'stamp-1')

        assert len(key) == SHA256_HEX_LENGTH
        assert set(key) <= set('0123456789abcdef')
