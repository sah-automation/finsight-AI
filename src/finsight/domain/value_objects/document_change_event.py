"""Immutable document change event used for cache invalidation and cascades."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from finsight.core.types import CompanyId, DocumentId

from .change_event_type import ChangeEventType

if TYPE_CHECKING:
    from datetime import datetime


def _require_text(value: object, name: str) -> str:
    text = '' if value is None else str(value).strip()
    if not text:
        raise ValueError(f'{name} is required on a change event')
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class DocumentChangeEvent:
    """A lifecycle change other components may react to (cache, cascade, audit)."""

    company_id: CompanyId
    document_id: DocumentId
    event_type: ChangeEventType
    version_id: str | None = None
    superseded_version_id: str | None = None
    category: str | None = None
    period: str | None = None
    job_id: str | None = None
    occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'company_id', CompanyId(_require_text(self.company_id, 'company_id'))
        )
        object.__setattr__(
            self, 'document_id', DocumentId(_require_text(self.document_id, 'document_id'))
        )
        object.__setattr__(self, 'event_type', ChangeEventType.normalize(self.event_type))
        object.__setattr__(self, 'version_id', _optional_text(self.version_id))
        object.__setattr__(
            self, 'superseded_version_id', _optional_text(self.superseded_version_id)
        )
        object.__setattr__(self, 'category', _optional_text(self.category))
        object.__setattr__(self, 'period', _optional_text(self.period))
        object.__setattr__(self, 'job_id', _optional_text(self.job_id))


__all__ = ['DocumentChangeEvent']
