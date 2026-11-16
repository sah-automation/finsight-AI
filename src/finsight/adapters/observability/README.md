# Observability Adapters

This directory contains adapters for the `ObservabilityExporterPort` interface.

## Adapters

- **CloudWatchExporter** (`cloud_watch_exporter.py`) — Pilot path (`observability_backend=cloudwatch`)
  - Exports spans to AWS CloudWatch via OTLP endpoint

- **OtlpEndpointExporter** (`otlp_endpoint_exporter.py`) — Standard path (`observability_backend=otlp_endpoint`)
  - Exports spans to a generic OTLP endpoint (e.g., Jaeger, Tempo, Datadog)

## Switch

The active adapter is selected via the `observability_backend` config switch in `envs.yaml`:

```yaml
observability_backend: cloudwatch  # or otlp_endpoint
```

## Contract Tests

See `tests/contract/observability/` for the port contract tests that both adapters must satisfy.
