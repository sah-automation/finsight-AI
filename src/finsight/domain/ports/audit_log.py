"""Port for append-only audit logging."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuditLog(ABC):
    """Append-only audit log port (source_view events and similar).

    The concrete call shape is intentionally tolerant: callers may pass a
    company id plus keyword fields describing the event. Implementations must
    persist the event without updating or deleting prior rows.
    """

    @abstractmethod
    async def append(  # noqa: PLR0913
        self,
        company_id: Any = None,
        *,
        event: Any = None,
        action: str | None = None,
        event_type: str | None = None,
        actor: Any = None,
        actor_id: Any = None,
        user_id: Any = None,
        user: Any = None,
        role: Any = None,
        citation_locator: Any = None,
        locator: Any = None,
        citation: Any = None,
        outcome: Any = None,
        status: Any = None,
        result: Any = None,
        trace: Any = None,
        trace_id: Any = None,
        resource_type: str | None = None,
        resource_id: Any = None,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Append one audit event (append-only).

        ``event`` may be a mapping/object carrying the full event payload.
        """
        _ = (
            company_id,
            event,
            action,
            event_type,
            actor,
            actor_id,
            user_id,
            user,
            role,
            citation_locator,
            locator,
            citation,
            outcome,
            status,
            result,
            trace,
            trace_id,
            resource_type,
            resource_id,
            details,
            metadata,
            kwargs,
        )
        raise NotImplementedError

    # Generic aliases.
    async def append_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    async def record(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    async def record_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    async def write(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if company_id is None and 'company_id' in kwargs:
            company_id = kwargs.pop('company_id')
        return await self.append(company_id, *args, **kwargs)

    async def write_event(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if company_id is None and 'company_id' in kwargs:
            company_id = kwargs.pop('company_id')
        return await self.append(company_id, *args, **kwargs)

    async def log(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    async def create(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if company_id is None and 'company_id' in kwargs:
            company_id = kwargs.pop('company_id')
        return await self.append(company_id, *args, **kwargs)

    async def emit(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    async def put(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append(*args, **kwargs)

    # Source-view specific convenience helpers.
    async def append_source_view(self, *args: Any, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('event_type', 'source_view')
        kwargs.setdefault('action', 'source_view')
        return await self.append(*args, **kwargs)

    async def record_source_view(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append_source_view(*args, **kwargs)

    async def log_source_view(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append_source_view(*args, **kwargs)

    async def write_source_view(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if company_id is None and 'company_id' in kwargs:
            company_id = kwargs.pop('company_id')
        return await self.append_source_view(company_id, *args, **kwargs)

    async def record_source_view_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self.append_source_view(*args, **kwargs)


# Backwards-friendly aliases.
AuditLogPort = AuditLog
AuditLogger = AuditLog
SourceViewAuditLog = AuditLog

__all__ = [
    'AuditLog',
    'AuditLogPort',
    'AuditLogger',
    'SourceViewAuditLog',
]
