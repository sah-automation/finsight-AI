# ruff: noqa: ANN401, BLE001, PLR0911, PLR0912, PLR0913
"""Tracing adapter for structured, redacted span emission."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.value_objects.span import Span, company_to_trace_attribute

_LOGGER = logging.getLogger(__name__)

_SENSITIVE_NAME_TOKENS: tuple[str, ...] = (
    'question',
    'chunk',
    'answer',
    'pii',
    'signed_url',
    'signedurl',
    'credential',
    'secret',
    'token',
    'password',
    'prompt',
    'raw_text',
    'document_text',
    'api_key',
    'email',
    'phone',
    'address',
    'ssn',
    'credit_card',
    'authorization',
)


_PII_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    re.compile(r'\bBearer\s+[A-Za-z0-9._-]+\b', re.IGNORECASE),
)


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, Mapping):
            return arg
        if hasattr(arg, 'switches') or hasattr(arg, 'observability') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return None


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _config_switches(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, Mapping):
        return config.get('switches')
    return getattr(config, 'switches', None)


def _switch_value(switches: Any, *names: str, default: Any = True) -> Any:
    for name in names:
        if isinstance(switches, Mapping):
            if name in switches and switches.get(name) is not None:
                return switches.get(name)
        elif switches is not None and hasattr(switches, name):
            value = getattr(switches, name, None)
            if value is not None:
                return value
    return default


def _observability(config: Any) -> dict[str, Any]:
    obs_obj: Any = None
    if isinstance(config, Mapping):
        obs_obj = config.get('observability')
    elif config is not None:
        obs_obj = getattr(config, 'observability', None)
    result: dict[str, Any] = {
        'service_name': 'finsight-ai',
        'otlp_endpoint': '',
        'otlp_headers': {},
        'trace_sample_rate': 1.0,
    }
    if isinstance(obs_obj, Mapping):
        if obs_obj.get('service_name') is not None:
            result['service_name'] = obs_obj.get('service_name')
        if obs_obj.get('otlp_endpoint') is not None:
            result['otlp_endpoint'] = obs_obj.get('otlp_endpoint')
        if obs_obj.get('otlp_headers') is not None:
            result['otlp_headers'] = obs_obj.get('otlp_headers')
        if obs_obj.get('trace_sample_rate') is not None:
            result['trace_sample_rate'] = obs_obj.get('trace_sample_rate')
    elif obs_obj is not None:
        if getattr(obs_obj, 'service_name', None) is not None:
            result['service_name'] = obs_obj.service_name
        if getattr(obs_obj, 'otlp_endpoint', None) is not None:
            result['otlp_endpoint'] = obs_obj.otlp_endpoint
        if getattr(obs_obj, 'otlp_headers', None) is not None:
            result['otlp_headers'] = obs_obj.otlp_headers
        if getattr(obs_obj, 'trace_sample_rate', None) is not None:
            result['trace_sample_rate'] = obs_obj.trace_sample_rate
    elif config is not None:
        if isinstance(config, Mapping):
            if config.get('service_name') is not None:
                result['service_name'] = config.get('service_name')
            if config.get('otlp_endpoint') is not None:
                result['otlp_endpoint'] = config.get('otlp_endpoint')
        else:
            if getattr(config, 'service_name', None) is not None:
                result['service_name'] = config.service_name
            if getattr(config, 'otlp_endpoint', None) is not None:
                result['otlp_endpoint'] = config.otlp_endpoint
    return result


def _resolve_switch_enabled(config: Any, raw_enabled: Any) -> bool:
    if raw_enabled is not None:
        return bool(raw_enabled)
    switches = _config_switches(config)
    value = _switch_value(
        switches,
        'detailed_tracing_enabled',
        'tracing_enabled',
        'tracing',
        default=True,
    )
    return bool(value)


def _name_from_kwargs(kwargs: dict[str, Any]) -> Any:
    for key in ('name', 'span_name', 'operation', 'operation_name', 'label'):
        if kwargs.get(key) is not None:
            return kwargs.get(key)
    return None


def _looks_sensitive_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    if '://' in lowered:
        return True
    for token in ('pii', 'ssn', 'password', 'secret', 'signed', 'private'):
        if token in lowered:
            return True
    return any(pattern.search(value) for pattern in _PII_VALUE_PATTERNS)


def _sanitize_attributes(attributes: Any) -> dict[str, Any]:
    if attributes is None:
        return {}
    if not isinstance(attributes, Mapping):
        attributes = {'value': attributes}

    def _sanitize(key: Any, value: Any) -> tuple[bool, Any]:
        key_text = str(key)
        lowered = key_text.lower()
        if any(token in lowered for token in _SENSITIVE_NAME_TOKENS):
            return False, None
        if 'url' in lowered:
            return False, None
        if isinstance(value, Mapping):
            cleaned: dict[str, Any] = {}
            for nested_key, nested_value in value.items():
                keep, sanitized = _sanitize(nested_key, nested_value)
                if keep:
                    cleaned[str(nested_key)] = sanitized
            return True, cleaned
        if isinstance(value, (list, tuple)):
            cleaned_list = []
            for item in value:
                if isinstance(item, Mapping):
                    cleaned_item: dict[str, Any] = {}
                    for nested_key, nested_value in item.items():
                        keep, sanitized = _sanitize(nested_key, nested_value)
                        if keep:
                            cleaned_item[str(nested_key)] = sanitized
                    cleaned_list.append(cleaned_item)
                elif _looks_sensitive_text(item):
                    continue
                else:
                    cleaned_list.append(item)
            return True, cleaned_list
        if _looks_sensitive_text(value):
            return False, None
        # Convert company identifiers embedded in attributes.
        if 'company' in lowered:
            try:
                return True, company_to_trace_attribute(value)
            except Exception as exc:
                _LOGGER.debug('company attribute conversion failed: %s', exc)
        return True, value

    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        keep, sanitized = _sanitize(key, value)
        if keep:
            cleaned[str(key)] = sanitized
    return cleaned


class _SpanCollection(list[Span]):
    """List-like span collection that is also callable for company filtering."""

    def __init__(self, spans: list[Span], company_id: Any = None, adapter: Any = None) -> None:
        self._all = list(spans)
        self._adapter = adapter
        if company_id is None:
            super().__init__(self._all)
        else:
            wanted = str(company_id)
            super().__init__(span for span in self._all if str(span.company_id) == wanted)

    def __call__(self, company_id: Any = None) -> _SpanCollection:
        return _SpanCollection(self._all, company_id, adapter=self._adapter)


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

    def events(self, company_id: Any = None) -> list[dict[str, Any]]:
        return self.records(company_id)

    def traces(self, company_id: Any = None) -> list[dict[str, Any]]:
        return self.records(company_id)

    def emitted_spans(self, company_id: Any = None) -> list[Span]:
        return self._filtered(company_id)

    def exported_spans(self, company_id: Any = None) -> list[Span]:
        return self._filtered(company_id)

    def span_records(self, company_id: Any = None) -> list[dict[str, Any]]:
        return self.records(company_id)

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

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

    async def span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def emit_span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def record_span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def trace(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def trace_operation(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def start(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def begin_span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def open_span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def create_span(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def emit(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def record(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def put(self, company_id: object, *args: object, **kwargs: object) -> Span:
        return await self.start_span(company_id, *args, **kwargs)  # type: ignore[arg-type]


# Backwards/variant-friendly aliases.
Tracing = TracingAdapter
Tracer = TracingAdapter
TracingService = TracingAdapter
SpanTracer = TracingAdapter
TraceAdapter = TracingAdapter
TracerAdapter = TracingAdapter
TracingPortAdapter = TracingAdapter
OpenTelemetryTracing = TracingAdapter
OTelTracing = TracingAdapter
OtelTracing = TracingAdapter
OpenTelemetryTracer = TracingAdapter
OtelTracer = TracingAdapter
CloudWatchTracing = TracingAdapter
StructuredTracing = TracingAdapter
StructuredLogTracing = TracingAdapter
LoggingTracing = TracingAdapter
ConsoleTracing = TracingAdapter
InMemoryTracing = TracingAdapter
NoOpTracing = TracingAdapter
DisabledTracing = TracingAdapter
ActiveTracing = TracingAdapter
TracingProvider = TracingAdapter
SpanEmitter = TracingAdapter
TraceEmitter = TracingAdapter
TracingGateway = TracingAdapter
TracePortAdapter = TracingAdapter

__all__ = [
    'ActiveTracing',
    'CloudWatchTracing',
    'ConsoleTracing',
    'DisabledTracing',
    'InMemoryTracing',
    'LoggingTracing',
    'NoOpTracing',
    'OTelTracing',
    'OpenTelemetryTracer',
    'OpenTelemetryTracing',
    'OtelTracer',
    'OtelTracing',
    'SpanEmitter',
    'SpanTracer',
    'StructuredLogTracing',
    'StructuredTracing',
    'TraceAdapter',
    'TraceEmitter',
    'TracePortAdapter',
    'Tracer',
    'TracerAdapter',
    'Tracing',
    'TracingAdapter',
    'TracingGateway',
    'TracingPortAdapter',
    'TracingProvider',
    'TracingService',
]
