# Glossary

| Term | Definition |
| --- | --- |
| Company | Tenant boundary; every query and data access must be scoped by `company_id`. |
| Document | Source file ingested into the system (PDF, DOCX, XLSX, CSV, etc.). |
| Chunk | Text segment extracted from a document for embedding and retrieval. |
| Metric | Raw figure extracted from a document, carrying its provenance: company, document, page, chunk, version, currency and units. Margin inputs (cost of goods sold, net income) are stored as Metrics so code computes gross/net margin percentages. _Avoid_: data point, raw value. |
| KPI | A code-computed, period-bucketed series derived from one or more Metrics. _Avoid_: measure, indicator. |
| ComputationStatus | The state of a KPI value: `computed` from available Metrics, `estimated` by spreading a source figure over a finer period, or `needs_review` because a required input is missing. _Avoid_: confidence, quality score. |
| EstimatedLabel | The `Estimated` marker on a KPI value spread from its DeclaredPeriod into a finer chart_period. _Avoid_: approximate, forecast, projection. |
| DeclaredPeriod | The period a source document states for a figure, distinct from the finer chart_period a KPI may be charted under. _Avoid_: chart period, bucket. |
| NeedsReview | The state of an item whose required inputs are missing; no value is guessed. Source conflicts keep both cited figures visible with labels, they are not `needs_review`. _Avoid_: pending, unverified. |
| Answer | Generated response to a question, grounded in evidence with citations. |
| Citation | Reference linking an answer back to a specific chunk/document. |
| Role | User permission level (`executive_leadership`, `corporate_finance_planners`, `audit_compliance`, `system_admin`). |
| Switch | Config-driven feature flag with both ON/OFF paths tested. |
| RAG | Retrieval-Augmented Generation combining vector/keyword search with LLM. |
| pgvector | PostgreSQL extension for vector similarity search. |
| Document library | Searchable collection of company documents with metadata and lifecycle actions. |
| Recycle bin | Temporary holding area for soft-deleted documents during `deleted_retention_days`. |
| Soft delete | Marking a document and its chunks unavailable to retrieval while retaining them for audit/restore. |
| Purge | Permanent removal of chunks, vectors, metrics and cache after retention or on demand. |
| Observability | Spans on every flow step, one usage row per paid call, and five §15 alarms; wired through ports so the backend can change without touching business code. |
| Trace | All spans sharing one trace id: one HTTP request correlated through its internal LLM/embedding/rerank calls to the final answer. |
| Span | Structured record for one operation with step name, duration, model name, retry count, cache hit, queue wait, active switch values and a hashed company id (ADR-0007). |
| TracedLLM | Decorator around the LLM gateway that emits an enriched span (tokens, fallback tags, cost) after each call; `TracedEmbedding` and `TracedReranker` do the same for their calls. |
| Metering | Exactly one usage row per paid call (company, service, units, cost, model, trace id); a paid call without a usage row is a bug. |
| MeteredLLM | Decorator that writes the usage row around an inner LLM gateway, so no call site can forget metering. |
| LLM Content Capture | The `llm_content_capture_enabled` switch gating full prompt/response and chunk text on spans (`gen_ai.*` attributes); on in dev/test, off in staging/prod, redaction blocklist always applies (ADR-0005). |
| OTLP | OpenTelemetry Protocol; the wire format spans are exported with to the CloudWatch Logs OTLP endpoint in AWS and the local collector in dev (ADR-0006). |
