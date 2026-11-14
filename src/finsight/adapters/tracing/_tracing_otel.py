"""OpenTelemetry OTLP/HTTP export helper for the tracing adapter.

This module is an adapter concern: it translates the domain-level ``Span``
value objects emitted by :class:`TracingAdapter` into OpenTelemetry spans and
exports them over OTLP/HTTP to the configured collector endpoint.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from collections.abc import Mapping
from typing import Any

from ._tracing_redaction import _sanitize_attributes as _redact_attributes

_LOGGER = logging.getLogger(__name__)

_OTEL_AVAILABLE = True
try:  # pragma: no cover - dependency is declared
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
except Exception as exc:  # pragma: no cover
    _OTEL_AVAILABLE = False
    _IMPORT_ERROR = exc


_TRACE_ID_HEX_LENGTH = 32


def _to_trace_id(value: Any) -> int:
    """Convert an application trace id into a 128-bit OTel trace id."""
    if value is None:
        return random.getrandbits(128)  # noqa: S311
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        trace_id = value & ((1 << 128) - 1)
        return trace_id or 1
    text = str(value)
    # Accept a 32-char hex trace id verbatim.
    if len(text) == _TRACE_ID_HEX_LENGTH:
        try:
            parsed = int(text, 16)
            if parsed:
                return parsed
        except ValueError:
            pass
    digest = hashlib.sha256(text.encode('utf-8')).digest()
    trace_id = int.from_bytes(digest[:16], 'big')
    return trace_id or 1


def _otel_value(value: Any) -> Any:
    """Convert a value into an OTel attribute value (primitive or list)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str, bytes)):
        return value
    if isinstance(value, Mapping):
        try:
            return json.dumps(value, default=str)
        except Exception:
            return str(value)
    if isinstance(value, (list, tuple)):
        converted: list[Any] = []
        for item in value:
            if isinstance(item, (bool, int, float, str, bytes)):
                converted.append(item)
            elif isinstance(item, Mapping):
                try:
                    converted.append(json.dumps(item, default=str))
                except Exception:
                    converted.append(str(item))
            else:
                converted.append(str(item))
        return converted
    return str(value)


def _otel_attributes(attributes: Any) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if not isinstance(attributes, Mapping):
        return cleaned
    # Apply the application redaction blocklist as a safety net.
    try:
        attributes = _redact_attributes(attributes)
    except Exception:
        pass
    if not isinstance(attributes, Mapping):
        return cleaned
    for key, value in attributes.items():
        key_text = str(key)
        lowered = key_text.lower()
        # Only hashed company identity may reach the wire.
        if 'company' in lowered and lowered not in {'company_hash', 'company_present'}:
            continue
        if 'tenant' in lowered:
            continue
        converted = _otel_value(value)
        if converted is None:
            continue
        cleaned[key_text] = converted
    return cleaned


class _OtelSpanExporter:
    """Thin wrapper around the OTLP/HTTP span exporter + batch processor."""

    def __init__(
        self,
        *,
        endpoint: Any = None,
        headers: Any = None,
        sample_rate: Any = 1.0,
        service_name: str = 'finsight-ai',
        timeout: float = 0.5,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers) if isinstance(headers, Mapping) else (headers or {})
        try:
            self.sample_rate = float(sample_rate if sample_rate is not None else 1.0)
        except (TypeError, ValueError):
            self.sample_rate = 1.0
        self.service_name = service_name or 'finsight-ai'
        self.timeout = float(timeout)

        self._enabled = False
        self._provider: Any = None
        self._processor: Any = None
        self._exporter: Any = None
        self._tracer: Any = None

        if not _OTEL_AVAILABLE:
            _LOGGER.debug('OpenTelemetry SDK unavailable: %s', _IMPORT_ERROR)
            return
        if not endpoint:
            return
        try:
            try:
                import requests
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry

                session = requests.Session()
                session.mount('http://', HTTPAdapter(max_retries=Retry(total=0)))
                session.mount('https://', HTTPAdapter(max_retries=Retry(total=0)))
            except Exception:
                session = None
            self._exporter = OTLPSpanExporter(
                endpoint=str(endpoint),
                headers=self.headers,
                timeout=self.timeout,
                session=session,
            )
            resource = Resource.create({'service.name': self.service_name})
            self._provider = TracerProvider(sampler=ALWAYS_ON, resource=resource)
            self._processor = BatchSpanProcessor(
                self._exporter,
                schedule_delay_millis=10,
                export_timeout_millis=int(self.timeout * 1000),
            )
            self._provider.add_span_processor(self._processor)
            self._tracer = self._provider.get_tracer('finsight')
            self._enabled = True
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.debug('OTel exporter init failed: %s', exc)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    @property
    def exporter(self) -> Any:
        return self._exporter

    @property
    def provider(self) -> Any:
        return self._provider

    @property
    def processor(self) -> Any:
        return self._processor

    @property
    def tracer(self) -> Any:
        return self._tracer

    def export_span(self, span: Any) -> None:
        # Thin public wrapper; heavy logic lives in the private method below.
        self._export_span(span)

    def _export_span(self, span: Any) -> None:
        if not self._enabled or self._tracer is None or self._processor is None:
            return
        # Sampling gate.
        if self.sample_rate <= 0.0:
            return
        if self.sample_rate < 1.0 and random.random() > self.sample_rate:  # noqa: S311
            return
        try:
            trace_id = _to_trace_id(getattr(span, 'trace_id', None))
            parent_span_id = random.getrandbits(64) or 1
            span_context = SpanContext(
                trace_id=trace_id,
                span_id=parent_span_id,
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            parent = NonRecordingSpan(span_context)
            context = _otel_trace.set_span_in_context(parent)

            name = (
                getattr(span, 'name', None)
                or getattr(span, 'span_name', None)
                or getattr(span, 'operation', None)
                or 'span'
            )
            attributes = _otel_attributes(_redact_attributes(getattr(span, 'attributes', {}) or {}))

            otel_span = self._tracer.start_span(str(name), context=context, attributes=attributes)
            try:
                # Propagate status as OK.
                from opentelemetry.trace import Status, StatusCode

                otel_span.set_status(Status(StatusCode.OK))
            except Exception:
                pass
            otel_span.end()

            try:
                self._processor.force_flush(timeout_millis=500)
            except Exception as exc:
                _LOGGER.debug('OTel force_flush failed: %s', exc)
        except Exception as exc:
            _LOGGER.debug('OTel span export failed: %s', exc)

    def flush(self) -> None:
        if self._processor is None:
            return
        try:
            self._processor.force_flush(timeout_millis=5000)
        except Exception as exc:
            _LOGGER.debug('OTel flush failed: %s', exc)

    def force_flush(self) -> None:
        self.flush()

    def shutdown(self) -> None:
        if self._processor is not None:
            try:
                self._processor.shutdown()
            except Exception as exc:
                _LOGGER.debug('OTel processor shutdown failed: %s', exc)
        if self._provider is not None:
            try:
                self._provider.shutdown()
            except Exception as exc:
                _LOGGER.debug('OTel provider shutdown failed: %s', exc)
        self._enabled = False

    def close(self) -> None:
        self.shutdown()


__all__ = ['_OtelSpanExporter', '_otel_attributes', '_to_trace_id']
