# ADR-0007: Every span carries the enriched observability schema

## Status

Accepted

## Context

`CODING_STANDARDS.md` section 15 requires every step of every flow to write a
trace span with step name, company id, duration, active switch values, model
name, retry count, cache hit and queue wait — and requires HTTP requests to be
correlated to the downstream LLM, embedding and rerank spans. Before the
observability work (#274–#278) a span carried whatever attributes its call
site happened to pass: there was no guaranteed set, no correlation id, and the
alert fields had no defined relationship to the span shape.

Two hard constraints apply. First, raw company ids must never appear as span
attributes (known-risk review: company isolation in observability data).
Second, the five section 15 alarms read specific JSON paths
(`$.span.attributes.*`), so the attribute names are effectively an interface
with production alarms attached (ADR-0006).

## Decision

- **Standard attribute set.** Every span guarantees the standard attributes:
  `step`, `company`, `duration`, `active_switch_values`, `model_name`,
  `retry_count`, `cache_hit`, `queue_wait` and `company_hash`
  (`STANDARD_SPAN_ATTRIBUTES`). The tracing adapter fills sensible defaults
  when call sites omit them — `cache_hit` false, `duration` from
  `duration_ms`, `queue_wait` from `queue_wait_ms`, and a snapshot of all
  switch values from config — so partial call sites still produce a complete
  span. `retry_count` and `retries` report the retries that actually happened:
  each retry loop records `last_retry_count`, and the traced decorators prefer
  that over the configured retry budget.
- **Hashed company identity.** Company identifiers are converted to trace
  attributes before anything is stored: `company_hash` (SHA-256 of the id) and
  `company_present`. Raw company ids are never placed in span attributes.
- **Decorator enrichment after the call.** The traced decorators
  (`TracedLLM`, `TracedEmbedding`, `TracedReranker`) enrich the span once the
  wrapped call completes: token counts (`tokens_prompt`, `tokens_completion`,
  `tokens_total`, plus alias spellings), fallback information
  (`fallback_tags`, `fallback_3_used`, `fallback_model_used`), `queue_wait`,
  and `estimated_cost` read from the last usage row, which links the span to
  its metering record.
- **HTTP correlation.** The correlation middleware opens one root span per
  request, named `http_request`, with `route`, `method`, `status_code`,
  `duration`, and, when present, `user_id` and `role`. It takes the trace id
  from the `x-request-id` header (or generates a UUID) and sets it as a
  contextvar; every downstream span is emitted under the same trace id, so one
  user question traces end to end from the API boundary.
- **Alert fields ride on attributes.** The alert signals
  (`fallback_3_used`, `reranker_down`, `embedding_retries`,
  `job_in_retry_list`, `role_cache_stale_seconds`) are span attributes, which
  is exactly what the section 15 metric filters read (ADR-0006).
- **Redaction applies to the whole set.** The ADR-0005 blocklist is enforced
  on every attribute set, in every `TracingPort` implementation, before a span
  is stored or exported. Content attributes (`genai.*`) join the schema only
  when `llm_content_capture_enabled` is on.

## Consequences

- Call sites may pass partial attributes; the adapter guarantees the schema,
  so dashboards, filters and eval tooling can rely on it.
- Attribute names are an interface: renaming a field that an alarm filter
  reads breaks production alerting, and the shape tests exist to fail the
  build when that happens. New attributes need the same care.
- Token-count keys are allow-listed as aggregates even though their names
  contain sensitive substrings; any similar future exception must be explicit
  in the redaction module, not ad hoc at call sites.
- Spans stay vendor-neutral behind `TracingPort`: the schema is what
  CloudWatch Logs ingests today and what any future backend (local Phoenix, a
  SaaS viewer) would receive unchanged.
