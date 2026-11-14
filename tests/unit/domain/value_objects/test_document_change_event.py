from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.value_objects import ChangeEventType, DocumentChangeEvent


def _event(**overrides: object) -> DocumentChangeEvent:
    values: dict[str, object] = {
        'company_id': CompanyId('company-a'),
        'document_id': DocumentId('doc-1'),
        'event_type': ChangeEventType.DOCUMENT_UPDATED,
        'version_id': 'version-2',
        'superseded_version_id': 'version-1',
    }
    values.update(overrides)
    return DocumentChangeEvent(**values)  # type: ignore[arg-type]


def test_event_carries_company_document_and_version_context() -> None:
    event = _event()

    assert event.company_id == 'company-a'
    assert event.document_id == 'doc-1'
    assert event.event_type == ChangeEventType.DOCUMENT_UPDATED
    assert event.version_id == 'version-2'
    assert event.superseded_version_id == 'version-1'


def test_event_type_normalises_plain_strings() -> None:
    event = _event(event_type='document.updated')

    assert event.event_type == ChangeEventType.DOCUMENT_UPDATED
    assert isinstance(event.event_type, ChangeEventType)


def test_unknown_event_type_fails_loudly() -> None:
    with pytest.raises(ValueError, match='event_type'):
        _event(event_type='document.exploded')


def test_event_requires_company_and_document() -> None:
    with pytest.raises(ValueError, match='company_id'):
        _event(company_id=CompanyId(''))
    with pytest.raises(ValueError, match='document_id'):
        _event(document_id=DocumentId(' '))


def test_event_is_frozen_and_compares_by_value() -> None:
    event = _event()

    assert event == _event()
    with pytest.raises(FrozenInstanceError):
        event.version_id = 'other'  # type: ignore[misc]


def test_known_event_types_are_available() -> None:
    expected = {
        ChangeEventType.DOCUMENT_UPDATED,
        ChangeEventType.DOCUMENT_DELETED,
        ChangeEventType.DOCUMENT_RESTORED,
        ChangeEventType.DOCUMENT_PURGED,
        ChangeEventType.DOCUMENT_REPROCESSED,
        ChangeEventType.CASCADE_REQUESTED,
    }

    assert {str(value) for value in expected} == {
        'document.updated',
        'document.deleted',
        'document.restored',
        'document.purged',
        'document.reprocessed',
        'cascade.requested',
    }
