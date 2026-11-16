"""Port for observability exporter implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ObservabilityExporterPort(ABC):
    """Interface for exporting telemetry data (traces, metrics, logs).

    Implementations handle different backends (CloudWatch, OTLP endpoint, etc.)
    but expose the same interface for emitting spans and other telemetry.
    """

    @abstractmethod
    def export_span(self, span: Any) -> None:
        """Export a span to the observability backend."""
        raise NotImplementedError

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered telemetry data."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the exporter and release resources."""
        raise NotImplementedError

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of the observability backend."""
        raise NotImplementedError

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Return whether the exporter is enabled."""
        raise NotImplementedError


# Aliases
ObservabilityExporter = ObservabilityExporterPort
TelemetryExporter = ObservabilityExporterPort
SpanExporter = ObservabilityExporterPort

__all__ = [
    'ObservabilityExporter',
    'ObservabilityExporterPort',
    'SpanExporter',
    'TelemetryExporter',
]
