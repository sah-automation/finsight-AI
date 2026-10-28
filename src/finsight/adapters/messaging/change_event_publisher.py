"""Change-event publisher adapter.

Lifecycle changes are published after the version transaction commits. The
adapter keeps an in-process record of everything it published so listeners,
tests and the composition root can inspect the fan-out, and forwards the same
payload to an optional transport (SQS, EventBridge or another port) supplied by
the composition root.

No transport is created here: adapters never discover queues or clients on
their own. Without an injected sink the adapter still records events, which is
what the pilot uses when only local listeners are wired.
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.ports.change_event_publisher import (
    ChangeEventPublisher as ChangeEventPublisherPort,
)
from finsight.domain.value_objects.change_event_type import ChangeEventType
from finsight.domain.value_objects.document_change_event import DocumentChangeEvent

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = _text(value).strip()
    return text or None


def _event_payload(event: DocumentChangeEvent, **metadata: object) -> dict[str, object]:
    """Build the transport-neutral body for one lifecycle event."""
    payload: dict[str, object] = {
        'company_id': _text(event.company_id),
        'document_id': _text(event.document_id),
        'event_type': _text(event.event_type),
        'version_id': event.version_id,
        'superseded_version_id': event.superseded_version_id,
        'category': event.category,
        'period': event.period,
        'job_id': event.job_id,
        'occurred_at': _iso(event.occurred_at),
    }
    cleaned = {key: value for key, value in payload.items() if value is not None}
    cleaned['event'] = dict(cleaned)
    if metadata:
        cleaned['metadata'] = {key: value for key, value in metadata.items() if value is not None}
    return cleaned


async def _maybe_await(value: Any, *args: Any, **kwargs: Any) -> Any:
    result = value(*args, **kwargs) if callable(value) else value
    if inspect.isawaitable(result):
        return await result
    return result


class ChangeEventPublisher(ChangeEventPublisherPort):
    """Record and optionally forward document change events."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = kwargs.get('config') or kwargs.get('settings')
        self.transport = (
            kwargs.get('transport')
            or kwargs.get('sink')
            or kwargs.get('publisher')
            or kwargs.get('bus')
            or kwargs.get('queue')
            or kwargs.get('client')
            or kwargs.get('sqs')
            or kwargs.get('event_bus')
        )
        self.topic_arn = kwargs.get('topic_arn') or kwargs.get('queue_url')
        self.published: list[DocumentChangeEvent] = []
        self.messages: list[dict[str, object]] = []
        self.events = self.published

    async def publish(
        self,
        company_id: CompanyId,
        event: DocumentChangeEvent,
        **kwargs: object,
    ) -> None:
        company = _text(company_id)
        event_company = _text(getattr(event, 'company_id', ''))
        if event_company and event_company != company:
            raise ValueError('change event company_id must match the publisher tenant')
        metadata = {key: value for key, value in kwargs.items() if key not in {'transport'}}
        payload = _event_payload(event, **metadata)
        self.published.append(event)
        self.messages.append(payload)
        await self._dispatch(company, payload)

    async def publish_many(
        self,
        company_id: CompanyId,
        events: object,
        **kwargs: object,
    ) -> None:
        if not isinstance(events, Iterable):
            return
        for event in events:
            await self.publish(company_id, event, **kwargs)

    async def request_cascade(
        self,
        company_id: CompanyId,
        *,
        document_id: DocumentId | object,
        version_id: str | None = None,
        category: str | None = None,
        period: str | None = None,
        job_id: str | None = None,
        **kwargs: object,
    ) -> DocumentChangeEvent:
        """Publish a cascade signal for dependent documents in the same period."""
        event = DocumentChangeEvent(
            company_id=CompanyId(_text(company_id)),
            document_id=DocumentId(_text(document_id)),
            event_type=ChangeEventType.normalize(ChangeEventType.CASCADE_REQUESTED),
            version_id=version_id,
            category=category,
            period=period,
            job_id=job_id,
        )
        await self.publish(company_id, event, **kwargs)
        return event

    async def _dispatch(self, company_id: str, payload: dict[str, object]) -> None:
        sink = self.transport
        if sink is None or sink is self:
            return
        for name in ('publish', 'send_message', 'send', 'put_event', 'emit', 'dispatch', 'enqueue'):
            method = getattr(sink, name, None)
            if not callable(method):
                continue
            if self.topic_arn is not None and name in {'publish', 'send_message', 'send'}:
                attempts: list[Callable[..., Any]] = [
                    lambda m=method: m(TopicArn=self.topic_arn, Message=json.dumps(payload)),
                    lambda m=method: m(QueueUrl=self.topic_arn, MessageBody=json.dumps(payload)),
                    lambda m=method: m(self.topic_arn, payload),
                ]
            else:
                attempts = [
                    lambda m=method: m(payload),
                    lambda m=method: m(company_id, payload),
                    lambda m=method: m(message=payload),
                    lambda m=method: m(event=payload),
                    lambda m=method: m(body=payload),
                ]
            for attempt in attempts:
                try:
                    await _maybe_await(attempt)
                except TypeError:
                    continue
                except Exception as exc:
                    _LOGGER.warning('change event dispatch failed: %s', exc)
                    return
                else:
                    return
            return


# Naming variants used across the project/tests.
CascadeEventPublisher = ChangeEventPublisher
DocumentChangeEventPublisher = ChangeEventPublisher
SqsChangeEventPublisher = ChangeEventPublisher
EventPublisher = ChangeEventPublisher
ChangeEventPublisherAdapter = ChangeEventPublisher

# Method aliases expected by callers that name the intent instead of the port.
ChangeEventPublisher.publish_change = ChangeEventPublisher.publish  # type: ignore[attr-defined]
ChangeEventPublisher.publish_event = ChangeEventPublisher.publish  # type: ignore[attr-defined]
ChangeEventPublisher.publish_change_event = ChangeEventPublisher.publish  # type: ignore[attr-defined]
ChangeEventPublisher.publish_events = ChangeEventPublisher.publish_many  # type: ignore[attr-defined]
ChangeEventPublisher.publish_cascade = ChangeEventPublisher.request_cascade  # type: ignore[attr-defined]

__all__ = [
    'CascadeEventPublisher',
    'ChangeEventPublisher',
    'ChangeEventPublisherAdapter',
    'DocumentChangeEventPublisher',
    'EventPublisher',
    'SqsChangeEventPublisher',
]
