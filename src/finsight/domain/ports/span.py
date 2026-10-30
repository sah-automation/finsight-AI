"""Convenience alias for the tracing port/span model."""

from __future__ import annotations

from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.value_objects.span import Span

__all__ = ['Span', 'TracingPort']
