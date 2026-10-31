# ruff: noqa: PLR0913
"""Port for emitting tracing spans (active and disabled modes)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from finsight.domain.value_objects.span import (
    Span,
    company_id_to_trace_attribute,
    company_to_trace_attribute,
    convert_company_id,
)


class TracingPort(ABC):
    """Interface for span emission.

    Implementations support active and disabled modes. Disabled mode still
    emits a minimal structured span. Company identifiers are converted to
    non-sensitive trace attributes by implementations.
    """

    @abstractmethod
    async def start_span(
        self,
        company_id: object,
        operation: str | None = None,
        *,
        name: str | None = None,
        span_name: str | None = None,
        trace_id: object = None,
        attributes: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        active: bool = True,
        enabled: bool | None = None,
        mode: str | None = None,
        minimal: bool | None = None,
        **kwargs: object,
    ) -> object:
        """Emit or start a span for an operation."""
        _ = (
            company_id,
            operation,
            name,
            span_name,
            trace_id,
            attributes,
            metadata,
            active,
            enabled,
            mode,
            minimal,
            kwargs,
        )
        raise NotImplementedError

    async def span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def emit_span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def record_span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def trace(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def trace_operation(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def start(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def begin_span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def open_span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def create_span(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def emit(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def record(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def put(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.start_span(company_id, *args, **kwargs)

    async def make_span(
        self,
        company_id: object,
        *args: object,
        **kwargs: object,
    ) -> Span:
        return Span(company_id=company_id, **kwargs)

    def to_trace_attribute(self, company_id: object) -> object:
        return company_to_trace_attribute(company_id)

    def convert_company_id(self, company_id: object) -> object:
        return company_to_trace_attribute(company_id)


# Aliases.
Tracer = TracingPort
Tracing = TracingPort
TracingService = TracingPort
SpanPort = TracingPort
SpanTracer = TracingPort
TracePort = TracingPort
TracingGateway = TracingPort
TraceEmitter = TracingPort
SpanEmitter = TracingPort
TraceRecorder = TracingPort
SpanRecorder = TracingPort

__all__ = [
    'SpanEmitter',
    'SpanPort',
    'SpanRecorder',
    'SpanTracer',
    'TraceEmitter',
    'TracePort',
    'TraceRecorder',
    'Tracer',
    'Tracing',
    'TracingGateway',
    'TracingPort',
    'TracingService',
    'company_id_to_trace_attribute',
    'company_to_trace_attribute',
    'convert_company_id',
]
