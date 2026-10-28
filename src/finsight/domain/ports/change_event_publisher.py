"""Port for publishing document change events and cascade signals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import CompanyId
    from finsight.domain.value_objects.document_change_event import DocumentChangeEvent


class ChangeEventPublisher(ABC):
    """Interface for fan-out of lifecycle changes; listeners stay decoupled."""

    @abstractmethod
    async def publish(
        self,
        company_id: CompanyId,
        event: DocumentChangeEvent,
        **kwargs: object,
    ) -> None:
        """Publish one change event for a company."""
        _ = (company_id, event, kwargs)
        raise NotImplementedError

    @abstractmethod
    async def publish_many(
        self,
        company_id: CompanyId,
        events: Sequence[DocumentChangeEvent],
        **kwargs: object,
    ) -> None:
        """Publish a batch of change events for a company."""
        _ = (company_id, events, kwargs)
        raise NotImplementedError


__all__ = ['ChangeEventPublisher']
