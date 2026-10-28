"""Contract tests for the AnswerCache port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.cache.answer_cache import AnswerCache
from finsight.core.types import CompanyId, DocumentCategory, DocumentId, Role
from finsight.domain.value_objects.change_event_type import ChangeEventType
from finsight.domain.value_objects.document_change_event import DocumentChangeEvent

if TYPE_CHECKING:
    from finsight.domain.ports import AnswerCache as AnswerCachePort

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


@pytest.fixture
def cache() -> AnswerCachePort:
    return AnswerCache(table_name='answer-cache-contract')


class TestAnswerCacheContract:
    async def test_round_trip_is_tenant_and_stamp_scoped(self, cache: AnswerCachePort) -> None:
        await cache.set(
            COMPANY,
            {'answer': 'Revenue was 100.'},
            question='What was revenue?',
            role=Role.CORPORATE_FINANCE_PLANNERS,
            access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
            document_stamp='stamp-1',
        )

        assert await cache.get(
            COMPANY,
            question='What was revenue?',
            role=Role.CORPORATE_FINANCE_PLANNERS,
            access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
            document_stamp='stamp-1',
        ) == {'answer': 'Revenue was 100.'}
        assert (
            await cache.get(
                COMPANY,
                question='What was revenue?',
                role=Role.CORPORATE_FINANCE_PLANNERS,
                access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
                document_stamp='stamp-2',
            )
            is None
        )
        assert (
            await cache.get(
                OTHER_COMPANY,
                question='What was revenue?',
                role=Role.CORPORATE_FINANCE_PLANNERS,
                access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
                document_stamp='stamp-1',
            )
            is None
        )

    async def test_key_includes_the_document_stamp(self, cache: AnswerCachePort) -> None:
        first = cache.build_key(  # type: ignore[attr-defined]
            COMPANY,
            question='What was revenue?',
            role=Role.CORPORATE_FINANCE_PLANNERS,
            access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
            document_stamp='stamp-1',
        )
        second = cache.build_key(  # type: ignore[attr-defined]
            COMPANY,
            question='What was revenue?',
            role=Role.CORPORATE_FINANCE_PLANNERS,
            access_scope=[DocumentCategory.FINANCIAL_STATEMENT],
            document_stamp='stamp-2',
        )

        assert first != second

    async def test_clear_removes_every_answer_for_a_company(self, cache: AnswerCachePort) -> None:
        await cache.set(COMPANY, 'one', key='one')
        await cache.set(COMPANY, 'two', key='two')
        await cache.set(OTHER_COMPANY, 'other', key='one')

        await cache.clear(COMPANY)

        assert await cache.get(COMPANY, key='one') is None
        assert await cache.get(COMPANY, key='two') is None
        assert await cache.get(OTHER_COMPANY, key='one') == 'other'

    async def test_lifecycle_events_clear_cached_answers(self, cache: AnswerCachePort) -> None:
        await cache.set(COMPANY, 'cached', key='answer')
        event = DocumentChangeEvent(
            company_id=COMPANY,
            document_id=DocumentId('document-a'),
            event_type=ChangeEventType.DOCUMENT_UPDATED,
        )

        cleared = await cache.handle_change_event(  # type: ignore[attr-defined]
            COMPANY, event
        )

        assert cleared is True
        assert await cache.get(COMPANY, key='answer') is None

    async def test_event_for_another_tenant_is_rejected(self, cache: AnswerCachePort) -> None:
        event = DocumentChangeEvent(
            company_id=OTHER_COMPANY,
            document_id=DocumentId('document-a'),
            event_type=ChangeEventType.DOCUMENT_DELETED,
        )

        with pytest.raises(ValueError):
            await cache.handle_change_event(COMPANY, event)  # type: ignore[attr-defined]

    async def test_explicit_delete_removes_one_entry(self, cache: AnswerCachePort) -> None:
        await cache.set(COMPANY, 'value', key='answer')

        assert await cache.delete(COMPANY, key='answer') is True
        assert await cache.get(COMPANY, key='answer') is None
