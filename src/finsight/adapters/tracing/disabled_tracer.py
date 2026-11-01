"""Disabled tracing adapter - emits minimal spans only."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.value_objects.span import Span, company_to_trace_attribute

_LOGGER = logging.getLogger(__name__)


class DisabledTracer(TracingPort):
    """No-op tracing adapter that emits minimal structured spans.

    This adapter implements TracingPort but does not send spans to any backend.
    It always returns minimal spans (mode='disabled', active=False, minimal=True)
    regardless of the active/enabled parameters, making it suitable for
    environments where detailed tracing is disabled.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the disabled tracer.

        Args:
            *args: Positional arguments (config, etc.) - accepted for compatibility
            **kwargs: Keyword arguments (config, service_name, etc.) - accepted for compatibility
        """
        # Accept config and other kwargs for interface compatibility,
        # but don't use them for any backend operations.
        self._config = kwargs.get('config') if isinstance(kwargs.get('config'), Mapping) else None
        self._service_name = kwargs.get('service_name', 'finsight-ai')
        self._spans: list[Span] = []

    async def _start_span_impl(  # noqa: PLR0913
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
    ) -> Span:
        """Create a minimal span (always disabled mode)."""
        # In disabled tracer, we always produce minimal spans regardless of parameters
        effective_mode = 'disabled'
        effective_active = False
        effective_minimal = True

        # Determine span name
        passed_name = name or span_name or operation
        if passed_name is None:
            op_name = kwargs.get('operation_name')
            label = kwargs.get('label')
            if isinstance(op_name, str):
                passed_name = op_name
            elif isinstance(label, str):
                passed_name = label

        # Merge attributes (for minimal spans, we still include company info)
        merged_attributes: dict[str, Any] = {}
        if isinstance(attributes, Mapping):
            merged_attributes.update(attributes)
        if isinstance(metadata, Mapping):
            merged_attributes.update(metadata)
        tags = kwargs.get('tags') or kwargs.get('context')
        if isinstance(tags, Mapping):
            merged_attributes.update(tags)

        # Add standard minimal attributes
        merged_attributes.setdefault('step', passed_name or operation)

        # Create minimal span
        span = Span(
            company_id=company_id,
            name=passed_name
            if passed_name is not None
            else (operation if operation is not None else None),
            span_name=passed_name,
            operation=passed_name,
            trace_id=trace_id if trace_id is not None else kwargs.get('trace'),
            attributes=merged_attributes,
            active=effective_active,
            enabled=effective_active,
            mode=effective_mode,
            minimal=effective_minimal,
        )

        # Ensure company identifiers are represented as non-sensitive attributes
        try:
            company_attr = company_to_trace_attribute(company_id)
            if isinstance(company_attr, Mapping):
                for key, value in company_attr.items():
                    span.attributes.setdefault(str(key), value)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug('company trace attribute conversion failed: %s', exc)

        # Store span for records/emitted_spans access
        self._spans.append(span)

        return span

    async def start_span(  # noqa: PLR0913
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
        """Emit or start a span for an operation (always minimal)."""
        return await self._start_span_impl(
            company_id=company_id,
            operation=operation,
            name=name,
            span_name=span_name,
            trace_id=trace_id,
            attributes=attributes,
            metadata=metadata,
            active=active,
            enabled=enabled,
            mode=mode,
            minimal=minimal,
            **kwargs,
        )

    def _filtered(self, company_id: Any = None) -> list[Span]:
        if company_id is None:
            return list(self._spans)
        wanted = str(company_id)
        return [span for span in self._spans if str(span.company_id) == wanted]

    def records(self, company_id: Any = None) -> list[dict[str, Any]]:
        """Return recorded spans as dicts."""
        return [span.to_dict() for span in self._filtered(company_id)]

    def emitted_spans(self, company_id: Any = None) -> list[Span]:
        """Return emitted spans as Span objects."""
        return self._filtered(company_id)

    async def make_span(
        self,
        company_id: object,
        *args: object,
        **kwargs: object,
    ) -> Span:
        """Create a minimal span without emitting (matches TracingAdapter behavior)."""
        # Always produce minimal span in disabled tracer
        kwargs['active'] = False
        kwargs['enabled'] = False
        kwargs['mode'] = 'disabled'
        kwargs['minimal'] = True
        raw_attributes = None
        for key in ('attributes', 'metadata', 'tags', 'context'):
            if key in kwargs and isinstance(kwargs.get(key), Mapping):
                raw_attributes = kwargs.pop(key)
                break
        kwargs['attributes'] = raw_attributes if isinstance(raw_attributes, Mapping) else {}
        span = Span(company_id=company_id, **kwargs)
        self._spans.append(span)
        return span


# Aliases for compatibility
InactiveTracer = DisabledTracer
MinimalTracer = DisabledTracer
NoOpTracer = DisabledTracer

__all__ = [
    'DisabledTracer',
    'InactiveTracer',
    'MinimalTracer',
    'NoOpTracer',
]
