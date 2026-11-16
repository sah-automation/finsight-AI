# Telemetry Adapters

This directory contains internal telemetry utilities for OpenTelemetry span handling.

## Modules

- **`_otel.py`** — OpenTelemetry span exporter setup and span attribute conversion
  - `_OtelSpanExporter`: Manages OTel provider, processor, and exporter lifecycle
  - `_otel_attributes()`: Converts span attributes to OTel-compatible format
  - `_sanitize_attributes()`: Redacts sensitive data from span attributes

- **`_redaction.py`** — Attribute sanitization/redaction logic
  - `_sanitize_attribute()`: Single attribute sanitization
  - Blocklist-based redaction for PII/secrets

## Usage

These are internal implementation details used by:
- `adapters/tracing/tracing_adapter.py` — For structured span emission
- `adapters/observability/*_exporter.py` — For exporting spans to backends

## Contract Tests

Telemetry utilities are tested indirectly through:
- `tests/contract/observability/` — Exporter contract tests
- `tests/unit/adapters/tracing/` — Tracing adapter behavior tests
