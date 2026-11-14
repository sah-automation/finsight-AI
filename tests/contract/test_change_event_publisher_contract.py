"""Contract tests for the ChangeEventPublisher port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.messaging.change_event_publisher import ChangeEventPublisher
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.value_objects.change_event_type import ChangeEventType
from finsight.domain.value_objects.document_change_event import DocumentChangeEvent

if TYPE_CHECKING:
    from finsight.domain.ports import ChangeEventPublisher as ChangeEventPublisherPort

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
DOCUMENT = DocumentId('document-a')


class _Sink:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send(self, message: object) -> None:
        self.messages.append(message)


def _event(event_type: str = ChangeEventType.DOCUMENT_UPDATED) -> DocumentChangeEvent:
    return DocumentChangeEvent(
        company_id=COMPANY,
        document_id=DOCUMENT,
        event_type=event_type,
        version_id='version-2',
        superseded_version_id='version-1',
        category='financial_statement',
        period='2026-Q1',
        job_id='job-1',
    )


@pytest.fixture
def publisher() -> ChangeEventPublisherPort:
    return ChangeEventPublisher()


class TestChangeEventPublisherContract:
    async def test_publish_records_the_event_and_payload(
        self, publisher: ChangeEventPublisherPort
    ) -> None:
        event = _event()

        await publisher.publish(COMPANY, event)

        recorded = publisher.published  # type: ignore[attr-defined]
        messages = publisher.messages  # type: ignore[attr-defined]
        assert recorded == [event]
        assert messages[0]['event_type'] == ChangeEventType.DOCUMENT_UPDATED
        assert messages[0]['version_id'] == 'version-2'
        assert messages[0]['superseded_version_id'] == 'version-1'

    async def test_publish_many_preserves_order(self, publisher: ChangeEventPublisherPort) -> None:
        events = [
            _event(ChangeEventType.DOCUMENT_UPDATED),
            _event(ChangeEventType.CASCADE_REQUESTED),
        ]

        await publisher.publish_many(COMPANY, events)

        assert publisher.published == events  # type: ignore[attr-defined]
        assert [message['event_type'] for message in publisher.messages] == [  # type: ignore[attr-defined]
            ChangeEventType.DOCUMENT_UPDATED,
            ChangeEventType.CASCADE_REQUESTED,
        ]

    async def test_publish_rejects_an_event_for_another_tenant(
        self, publisher: ChangeEventPublisherPort
    ) -> None:
        event = DocumentChangeEvent(
            company_id=OTHER_COMPANY,
            document_id=DOCUMENT,
            event_type=ChangeEventType.DOCUMENT_DELETED,
        )

        with pytest.raises(ValueError):
            await publisher.publish(COMPANY, event)

    async def test_optional_sink_receives_the_payload(self) -> None:
        sink = _Sink()
        publisher = ChangeEventPublisher(transport=sink)

        await publisher.publish(COMPANY, _event())

        assert len(sink.messages) == 1

    async def test_cascade_signal_uses_the_cascade_event_type(self) -> None:
        publisher = ChangeEventPublisher()

        event = await publisher.request_cascade(  # type: ignore[attr-defined]
            COMPANY,
            document_id=DOCUMENT,
            category='financial_statement',
            period='2026-Q1',
        )

        assert event.event_type == ChangeEventType.CASCADE_REQUESTED
        assert publisher.messages[0]['event_type'] == ChangeEventType.CASCADE_REQUESTED  # type: ignore[attr-defined]
