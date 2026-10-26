"""Security tests for tenant-scoped answer cache keys."""

from __future__ import annotations

import pytest

from finsight.core.types import Category, RequestContext, Role
from finsight.domain.services.cache_key import build_answer_cache_key

pytestmark = pytest.mark.security

SHA256_HEX_LENGTH = 64


def _context(
    company_id: str = 'company-a',
    role: Role = Role.CORPORATE_FINANCE_PLANNERS,
    access_scope: list[Category] | None = None,
) -> RequestContext:
    return RequestContext(
        company_id=company_id,
        user_id='user-a',
        role=role,
        trace_id='trace-a',
        permissions={},
        access_scope=access_scope or [Category.METRICS, Category.FINANCIALS],
    )


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
            _context(access_scope=[Category.METRICS]), 'What is revenue?', 'stamp-1'
        )
        second = build_answer_cache_key(
            _context(access_scope=[Category.METRICS, Category.FINANCIALS]),
            'What is revenue?',
            'stamp-1',
        )

        assert first != second

    def test_access_scope_order_does_not_matter(self) -> None:
        first = build_answer_cache_key(
            _context(access_scope=[Category.METRICS, Category.FINANCIALS]),
            'What is revenue?',
            'stamp-1',
        )
        second = build_answer_cache_key(
            _context(access_scope=[Category.FINANCIALS, Category.METRICS]),
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
