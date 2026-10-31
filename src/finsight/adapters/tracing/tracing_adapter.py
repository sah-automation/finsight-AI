# ruff: noqa: BLE001, PLR0912, PLR0913
"""Tracing adapter for structured, redacted span emission."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.value_objects.span import Span, company_to_trace_attribute

from ._tracing_config import (
    _config_switches,
    _first,
    _name_from_kwargs,
    _observability,
    _resolve_config,
    _resolve_switch_enabled,
)
from ._tracing_redaction import (
    _sanitize_attributes,
)
from ._tracing_span_collection import _SpanCollection

_LOGGER = logging.getLogger(__name__)


class TracingAdapter(TracingPort):
    """Vendor adapter implementing TracingPort."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)
        _config_switches(self.config)

        raw_enabled = _first(
            kwargs,
            'enabled',
            'active',
            'detailed_tracing_enabled',
            'detailed_tracing',
            'tracing_enabled',
            'tracing',
            default=None,
        )
        self.enabled = _resolve_switch_enabled(self.config, raw_enabled)
        self.detailed_tracing_enabled = self.enabled

        obs = _observability(self.config)
        self.service_name = _first(kwargs, 'service_name', default=obs.get('service_name'))
        self.otlp_endpoint = _first(
            kwargs, 'otlp_endpoint', 'endpoint', default=obs.get('otlp_endpoint')
        )
        self.otlp_headers = _first(
            kwargs, 'otlp_headers', 'headers', default=obs.get('otlp_headers')
        )
        self.trace_sample_rate = _first(
            kwargs, 'trace_sample_rate', 'sample_rate', default=obs.get('trace_sample_rate')
        )

        tracing_name = _first(kwargs, 'table_name', 'name', default=None)
        self.name = tracing_name or self.service_name

        self._spans: list[Span] = []

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _filtered(self, company_id: Any = None) -> list[Span]:
        if company_id is None:
            return list(self._spans)
        wanted = str(company_id)
        return [span for span in self._spans if str(span.company_id) == wanted]

    @property
    def spans(self) -> _SpanCollection:
        return _SpanCollection(self._spans, adapter=self)

    def records(self, company_id: Any = None) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self._filtered(company_id)]

    def emitted_spans(self, company_id: Any = None) -> list[Span]:
        return self._filtered(company_id)

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def start_span(self, *args: Any, **kwargs: Any) -> Any:
        return await self._start_span_impl(*args, **kwargs)

    async def _start_span_impl(
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
        effective_active = bool(self.enabled) and bool(active)
        if enabled is not None:
            effective_active = bool(enabled) and bool(active)
        disabled = kwargs.get('disabled')
        if disabled is True:
            effective_active = False
        if mode is not None:
            lowered = str(mode).lower()
            if lowered in {'disabled', 'off', 'inactive', 'false', 'minimal'}:
                effective_active = False
            elif lowered in {'active', 'on', 'enabled', 'true'}:
                effective_active = effective_active and True
        if minimal is True:
            effective_active = False

        passed_name = _name_from_kwargs(
            {
                'name': name,
                'span_name': span_name,
                'operation': operation,
                **{k: v for k, v in kwargs.items() if k in {'operation_name', 'label'}},
            }
        )
        if passed_name is None:
            passed_name = _first(
                kwargs, 'name', 'span_name', 'operation', 'operation_name', 'label', default=None
            )

        merged_attributes: dict[str, Any] = {}
        if isinstance(attributes, Mapping):
            merged_attributes.update(attributes)
        if isinstance(metadata, Mapping):
            merged_attributes.update(metadata)
        tags = kwargs.get('tags') or kwargs.get('context')
        if isinstance(tags, Mapping):
            merged_attributes.update(tags)
        for key, value in kwargs.items():
            if key in {
                'attributes',
                'metadata',
                'tags',
                'context',
                'active',
                'enabled',
                'disabled',
                'mode',
                'minimal',
                'name',
                'span_name',
                'operation',
                'operation_name',
                'label',
                'trace_id',
                'trace',
                'trace_identifier',
            }:
                continue
            merged_attributes[key] = value

        sanitized = _sanitize_attributes(merged_attributes) if effective_active else {}

        span = Span(
            company_id=company_id,
            name=passed_name
            if passed_name is not None
            else (operation if operation is not None else None),
            span_name=passed_name,
            operation=passed_name,
            trace_id=trace_id if trace_id is not None else kwargs.get('trace'),
            attributes=sanitized,
            active=effective_active,
            enabled=effective_active,
            mode='active' if effective_active else 'disabled',
            minimal=not effective_active,
        )

        if not effective_active:
            span.minimal = True

        # Ensure company identifiers are represented as non-sensitive attributes.
        try:
            company_attr = company_to_trace_attribute(company_id)
            if isinstance(company_attr, Mapping):
                for key, value in company_attr.items():
                    span.attributes.setdefault(str(key), value)
        except Exception as exc:
            _LOGGER.debug('company trace attribute conversion failed: %s', exc)

        self._spans.append(span)

        try:
            _LOGGER.info(
                'tracing span emitted',
                extra={'span': span.to_dict(), 'service': self.service_name},
            )
        except Exception as exc:
            _LOGGER.debug('tracing log emission failed: %s', exc)

        return span

    async def make_span(
        self,
        company_id: object,
        *args: object,
        **kwargs: object,
    ) -> Span:
        raw_attributes = None
        for key in ('attributes', 'metadata', 'tags', 'context'):
            if key in kwargs and isinstance(kwargs.get(key), Mapping):
                raw_attributes = kwargs.pop(key)
                break
        kwargs['attributes'] = _sanitize_attributes(raw_attributes)
        if 'active' not in kwargs and 'enabled' not in kwargs:
            kwargs['active'] = self.enabled
        return Span(company_id=company_id, **kwargs)

    async def span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def emit_span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def record_span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def trace(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def trace_operation(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def start(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def begin_span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def open_span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def create_span(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def emit(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def record(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]

    async def put(self, company_id: object, *args: Any, **kwargs: Any) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[no-any-return]


_alias_names = [
    'Tracing',
    'Tracer',
    'TracingService',
    'SpanTracer',
    'TraceAdapter',
    'TracerAdapter',
    'TracingPortAdapter',
    'OpenTelemetryTracing',
    'OTelTracing',
    'OtelTracing',
    'OpenTelemetryTracer',
    'OtelTracer',
    'CloudWatchTracing',
    'StructuredTracing',
    'StructuredLogTracing',
    'LoggingTracing',
    'ConsoleTracing',
    'InMemoryTracing',
    'NoOpTracing',
    'DisabledTracing',
    'ActiveTracing',
    'TracingProvider',
    'SpanEmitter',
    'TraceEmitter',
    'TracingGateway',
    'TracePortAdapter',
]
for _n in ('events', 'traces', 'span_records'):
    setattr(TracingAdapter, _n, TracingAdapter.records)
for _n in ('exported_spans',):
    setattr(TracingAdapter, _n, TracingAdapter.emitted_spans)

for _name in _alias_names:
    globals()[_name] = TracingAdapter
__all__ = [*_alias_names, 'TracingAdapter']  # noqa: PLE0604
