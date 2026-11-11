# ADR-0006: Trace spans flow to AWS over OTLP into CloudWatch Logs

## Status

Accepted

## Context

The five degradation alarms required by `CODING_STANDARDS.md` section 15
(fallback model 3 used, reranker down, embedding retries exceeded, job in
retry list, role cache stale) already exist as CloudWatch metric filters and
alarms in `infra/cdk/stacks/observability.py`. Their filter patterns match
structured JSON paths — `$.span.attributes.*` and the same fields at the top
level of a log record. Until observability was wired (#276), those filters
matched no real log shape: tracing spans lived in an in-memory list and OTel
dependencies were declared but never used.

The AWS-native path research (#271) compared four options: an ADOT Lambda
layer exporting to X-Ray, OTLP into CloudWatch Logs, an ADOT collector sidecar
(not Lambda-native), and a self-hosted Grafana Tempo stack. Constraints: AWS
infrastructure as code (ADR-0002), zero paid services, and no redesign of the
existing alarms.

## Decision

Spans are exported with **OTLP to the CloudWatch Logs OTLP endpoint**:

- The endpoint is `https://logs.{region}.amazonaws.com/v1/logs`, with the
  region taken from the CDK stack. No account or region is hard-coded
  (ADR-0002).
- `ComputeStack` gives the Lambda `OTLP_ENDPOINT` and `ENVIRONMENT`
  environment variables. `AWS_REGION` is intentionally not declared: the
  Lambda runtime reserves and injects it.
- IAM access is scoped to the Observability log group only: the runtime role
  gets `logs:CreateLogStream` and `logs:PutLogEvents` (`grant_write`), nothing
  broader.
- Independently of OTLP export, every emitted span is written as one
  structured JSON log record (`tracing span emitted`) through the JSON log
  formatter, with the span nested under `span` and its attributes under
  `span.attributes`. The five section 15 metric filters read exactly those
  paths, so they fire whether an event arrives via OTLP ingestion or the
  structured log path. The log shape is locked by
  `tests/unit/adapters/tracing/test_span_log_shape.py`; renaming a field there
  silently breaks an alarm and must fail a test.
- The log group `/aws/lambda/finsight-{env}` carries a retention policy
  (one month; prod retains on delete), so trace data has a bounded keep time.
- Local development keeps `observability.otlp_endpoint` empty and uses the
  OTel collector in docker-compose. A local Arize Phoenix viewer is a separate
  work item (#280) and changes only where dev spans are sent, not the port,
  schema or production path.

## Consequences

- The five section 15 alarms fire on real span data with no new alarm design.
- CloudWatch Logs ingestion is billed per GB. With content capture off in
  staging and production by default (ADR-0005), volume stays predictable.
- The OTel SDK is declared in `pyproject.toml` but not yet vendored into the
  Lambda zip; dependency vendoring remains DI-21. Until then the OTLP wiring
  is exercised by infrastructure tests, and the structured log path is the
  live alarm data source.
- CloudWatch Logs is not a trace UI: span search and inspection are limited
  compared with a dedicated trace viewer. That is acceptable while the primary
  need is alarms; if a viewer is added later, it slots in behind `TracingPort`
  and only the endpoint changes.
