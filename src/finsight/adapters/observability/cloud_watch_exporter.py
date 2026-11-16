"""CloudWatch observability exporter adapter (pilot path).

This adapter uses the same OTLP exporter code as the standard path,
but points at the CloudWatch Logs OTLP endpoint with routing headers.
"""

from __future__ import annotations

import logging
from typing import Any

from finsight.adapters.telemetry import _OtelSpanExporter
from finsight.domain.ports.observability_exporter_port import ObservabilityExporterPort

_LOGGER = logging.getLogger(__name__)


class CloudWatchExporter(ObservabilityExporterPort):
    """CloudWatch Logs OTLP exporter (pilot implementation).

    Uses the generic OTLP/HTTP exporter pointed at the CloudWatch Logs
    OTLP endpoint with x-aws-logs-group and x-aws-logs-stream headers.
    """

    """CloudWatch Logs OTLP exporter (pilot implementation).

    Uses the generic OTLP/HTTP exporter pointed at the CloudWatch Logs
    OTLP endpoint with x-aws-logs-group and x-aws-logs-stream headers.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        headers: dict[str, str] | None = None,
        sample_rate: float = 1.0,
        service_name: str = 'finsight-ai',
        timeout: float = 0.5,
    ) -> None:
        self._endpoint = endpoint
        self._headers = dict(headers) if headers else {}
        self._sample_rate = sample_rate
        self._service_name = service_name
        self._timeout = timeout

        self._exporter: _OtelSpanExporter | None = None
        self._enabled = False
        self._init_exporter()

    def _init_exporter(self) -> None:
        """Initialize the OTLP exporter with CloudWatch configuration."""
        try:
            self._exporter = _OtelSpanExporter(
                endpoint=self._endpoint,
                headers=self._headers,
                sample_rate=self._sample_rate,
                service_name=self._service_name,
                timeout=self._timeout,
            )
            self._enabled = getattr(self._exporter, 'enabled', False)
            if self._enabled:
                _LOGGER.info(
                    'CloudWatch OTLP exporter initialized',
                    extra={
                        'endpoint': self._endpoint,
                        'service_name': self._service_name,
                        'backend': 'cloudwatch',
                    },
                )
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.debug('CloudWatch OTLP exporter init failed: %s', exc)
            self._enabled = False

    @property
    def backend_name(self) -> str:
        return 'cloudwatch'

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._headers)

    @property
    def sample_rate(self) -> float:
        return self._sample_rate

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def otel_exporter(self) -> Any:
        return getattr(self._exporter, 'exporter', None) if self._exporter else None

    @property
    def otel_provider(self) -> Any:
        return getattr(self._exporter, 'provider', None) if self._exporter else None

    @property
    def otel_processor(self) -> Any:
        return getattr(self._exporter, 'processor', None) if self._exporter else None

    @property
    def otel_tracer(self) -> Any:
        return getattr(self._exporter, 'tracer', None) if self._exporter else None

    def export_span(self, span: Any) -> None:
        """Export a span to CloudWatch Logs via OTLP."""
        if self._exporter is not None and self._enabled:
            try:
                self._exporter.export_span(span)
            except Exception as exc:  # pragma: no cover - defensive
                _LOGGER.debug('CloudWatch OTLP export failed: %s', exc)

    def flush(self) -> None:
        """Flush any buffered spans."""
        if self._exporter is not None:
            try:
                self._exporter.flush()
            except Exception as exc:  # pragma: no cover - defensive
                _LOGGER.debug('CloudWatch OTLP flush failed: %s', exc)

    def shutdown(self) -> None:
        """Shutdown the exporter and release resources."""
        if self._exporter is not None:
            try:
                self._exporter.shutdown()
            except Exception as exc:  # pragma: no cover - defensive
                _LOGGER.debug('CloudWatch OTLP shutdown failed: %s', exc)
            self._exporter = None
            self._enabled = False


__all__ = ['CloudWatchExporter']
