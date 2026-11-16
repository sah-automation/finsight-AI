# Telemetry Shared Utilities

This package contains shared telemetry utilities used by multiple adapters.

## Contents

### `_OtelSpanExporter` (`_otel.py`)

Thin wrapper around the OpenTelemetry OTLP/HTTP span exporter + batch processor.

This is a shared implementation used by:
- `CloudWatchExporter` (in `finsight.adapters.observability`)
- `OtlpEndpointExporter` (in `finsight.adapters.observability`)

The shared location avoids circular imports between `tracing_adapter.py` and the observability adapters.

## Functions

- `_to_trace_id(value)` - Convert application trace ID to 128-bit OTel trace ID
- `_otel_value(value)` - Convert value to OTel attribute value (primitive or list)
- `_otel_attributes(attributes)` - Convert attributes dict to OTel format with redaction

## Architecture Note

This module exists to break the circular dependency:
```
tracing_adapter.py → CloudWatchExporter/OtlpEndpointExporter → _OtelSpanExporter
```

Previously `_OtelSpanExporter` was in `tracing._tracing_otel`, but that created a cycle because `tracing_adapter` imports the observability adapters, which imported `_OtelSpanExporter` from `tracing`.
