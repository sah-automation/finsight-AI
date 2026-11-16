# Observability Adapters

This package contains adapters for exporting telemetry data (traces, metrics, logs) to different observability backends.

## Adapters

### CloudWatchExporter (`cloud_watch_exporter.py`)

Pilot implementation that exports to AWS CloudWatch Logs via the OTLP endpoint.

- Endpoint: `https://logs.{region}.amazonaws.com/v1/logs`
- Headers: `x-aws-logs-group`, `x-aws-logs-stream`
- Used when `observability_backend` switch is set to `cloudwatch`

### OtlpEndpointExporter (`otlp_endpoint_exporter.py`)

Standard implementation that exports to a generic OTLP endpoint.

- Endpoint: Configurable (e.g., `https://otel.example.com/v1/traces`)
- Headers: Configurable (e.g., authorization headers)
- Used when `observability_backend` switch is set to `otlp_endpoint`

## Configuration

Both adapters use the same underlying OTLP/HTTP exporter (`_OtelSpanExporter`) but are configured with different endpoints and headers based on the `observability_backend` switch in `SwitchesConfig`.

The observability configuration in `ObservabilityConfig` supports:
- `cloudwatch_otlp_endpoint` / `cloudwatch_otlp_headers` - for CloudWatch backend
- `otlp_endpoint_endpoint` / `otlp_endpoint_headers` - for OTLP endpoint backend
- Legacy `otlp_endpoint` / `otlp_headers` - fallback for both backends

## Contract Tests

Both adapters must pass the contract tests in `tests/contract/observability/test_observability_exporter_contract.py`.
