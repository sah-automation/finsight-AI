"""Change event type enum for document lifecycle signals (pure domain)."""

from __future__ import annotations


class ChangeEventType(str):
    """String-backed event type published after a document lifecycle change."""

    DOCUMENT_UPDATED = 'document.updated'
    DOCUMENT_DELETED = 'document.deleted'
    DOCUMENT_RESTORED = 'document.restored'
    DOCUMENT_PURGED = 'document.purged'
    DOCUMENT_REPROCESSED = 'document.reprocessed'
    CASCADE_REQUESTED = 'cascade.requested'

    _VALUES = frozenset(
        {
            DOCUMENT_UPDATED,
            DOCUMENT_DELETED,
            DOCUMENT_RESTORED,
            DOCUMENT_PURGED,
            DOCUMENT_REPROCESSED,
            CASCADE_REQUESTED,
        }
    )

    def __new__(cls, value: object) -> ChangeEventType:
        canonical = '' if value is None else str(value).strip().lower()
        if canonical not in cls._VALUES:
            raise ValueError(f'Unknown event_type {value!r}')
        return str.__new__(cls, canonical)

    @classmethod
    def normalize(cls, value: object) -> ChangeEventType:
        """Return a validated event type, accepting strings and enum members."""
        if isinstance(value, ChangeEventType):
            return value
        return cls(value)


__all__ = ['ChangeEventType']
