# Local Trace Viewer Comparison — Research for Issue #267

**Repo norms:** docker-compose, zero paid services, OTel-native, `make docker-up` already runs OTel collector (ports 4317/4318), Python 3.12, uv, LiteLLM gateway.

---

## 1. Langfuse OSS (self-hosted)

| Aspect | Details |
|--------|---------|
| **docker-compose snippet** | ```yaml\nservices:\n  langfuse-web:\n    image: langfuse/langfuse:3\n    ports:\n      - "3000:3000"\n    environment:\n      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/langfuse\n      - NEXTAUTH_URL=http://localhost:3000\n      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}\n      - SALT=${SALT}\n      - ENCRYPTION_KEY=${ENCRYPTION_KEY}\n      - CLICKHOUSE_URL=http://clickhouse:8123\n      - CLICKHOUSE_USER=default\n      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}  # pragma: allowlist secret\n      - REDIS_CONNECTION_STRING=redis://redis:6379\n      - LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse\n      - LANGFUSE_S3_ENDPOINT=http://minio:9000\n      - LANGFUSE_S3_ACCESS_KEY_ID=minioadmin  # pragma: allowlist secret\n      - LANGFUSE_S3_SECRET_ACCESS_KEY=minioadmin  # pragma: allowlist secret\n    depends_on:\n      - postgres\n      - clickhouse\n      - redis\n      - minio\n    volumes:\n      - langfuse-data:/data\n  langfuse-worker:\n    image: langfuse/langfuse:3\n    command: worker\n    environment: *same as web*\n    depends_on:\n      - postgres\n      - clickhouse\n      - redis\n      - minio\n  postgres:\n    image: pgvector/pgvector:pg16\n    environment:\n      - POSTGRES_DB=langfuse\n      - POSTGRES_USER=postgres\n      - POSTGRES_PASSWORD=postgres  # pragma: allowlist secret\n    volumes:\n      - pg-langfuse:/var/lib/postgresql/data\n  clickhouse:\n    image: clickhouse/clickhouse-server:24.8\n    environment:\n      - CLICKHOUSE_DB=langfuse\n      - CLICKHOUSE_USER=default\n      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}  # pragma: allowlist secret\n    volumes:\n      - clickhouse-data:/var/lib/clickhouse\n      - ./infra/clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql\n    ulimits:\n      nofile: 262144\n  redis:\n    image: redis:7-alpine\n    volumes:\n      - redis-langfuse:/data\n  minio:\n    image: minio/minio:latest\n    command: server /data --console-address ":9001"\n    environment:\n      - MINIO_ROOT_USER=minioadmin  # pragma: allowlist secret\n      - MINIO_ROOT_PASSWORD=minioadmin  # pragma: allowlist secret\n    ports:\n      - "9000:9000"\n      - "9001:9001"\n    volumes:\n      - minio-data:/data\nvolumes:\n  pg-langfuse:\n  clickhouse-data:\n  redis-langfuse:\n  minio-data:\n  langfuse-data:\n``` |
| **OTLP endpoint for app** | `http://otel-collector:4318/v1/traces` (OTLP HTTP) — the app sends to the existing OTel collector; collector forwards to Langfuse via OTLP HTTP exporter pointed at `langfuse-web:3000/api/public/otel/v1/traces` |
| **Resource footprint** | **High**: 6 containers (web, worker, postgres, clickhouse, redis, minio). ClickHouse alone needs ~2–4 GB RAM, 2 CPU. Total ~3–5 GB RAM, 4+ CPU cores. Not suitable for CI or low-resource laptops. |
| **How traces appear** | Full-featured web UI at `http://localhost:3000`. Trace waterfall, span details, prompt/response playground, evaluations, datasets, prompt management. |
| **Prompt/response content** | ✅ Yes — captures full prompt, completion, token counts, model params. Has a "prompt playground" and "trace inspector" with raw JSON. |
| **Content-capture switch** | Works natively. Langfuse SDKs redact PII via config; the repo's existing `SENSITIVE_SPAN_FIELDS` redaction blocklist can be mirrored in Langfuse's `LANGFUSE_REDACTION_KEYS` env var. |
| **Python deps / migration friction** | **High friction**: Requires `langfuse` Python SDK (`pip install langfuse`) and replacing the current `TracingAdapter` backend with Langfuse's `observe()` decorator or manual `langfuse.trace()` calls. The repo's port/adapter pattern (`TracingPort` → `TracingAdapter`) would need a new `LangfuseTracingAdapter` that wraps the SDK. In-memory spans (`_spans` list) would be deprecated. Existing contract tests in `tests/contract/test_tracing_contract.py` would need updates. |
| **Repo-specific notes** | - Adds 5 new services to `docker-compose.test.yml` (or a new `docker-compose.langfuse.yml`).<br>- Requires generating `NEXTAUTH_SECRET`, `SALT`, `ENCRYPTION_KEY`, `CLICKHOUSE_PASSWORD` secrets.<br>- ClickHouse ulimit `nofile: 262144` may fail on macOS Docker Desktop without `--ulimit`.<br>- The repo already has `pgvector/pgvector:pg16` for the main DB; Langfuse needs its own Postgres instance (or shared with schema prefix).<br>- Migration from current in-memory spans: **breaking** — all span emission code paths go through `TracingAdapter._start_span_impl` → `record_tracing_backend_span`. A new backend would replace the no-op `record_tracing_backend_span`. |

---

## 2. Arize Phoenix (self-hosted)

| Aspect | Details |
|--------|---------|
| **docker-compose snippet** | ```yaml\nservices:\n  phoenix:\n    image: arizephoenix/phoenix:latest\n    ports:\n      - "6006:6006"\n    environment:\n      - PHOENIX_WORKING_DIR=/mnt/data\n      - PHOENIX_SQL_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/phoenix\n      - PHOENIX_OTLP_ENDPOINT=http://otel-collector:4318\n    volumes:\n      - phoenix-data:/mnt/data\n    depends_on:\n      - postgres\n  postgres:\n    image: pgvector/pgvector:pg16\n    environment:\n      - POSTGRES_DB=phoenix\n      - POSTGRES_USER=postgres\n      - POSTGRES_PASSWORD=postgres  # pragma: allowlist secret\n    volumes:\n      - pg-phoenix:/var/lib/postgresql/data\nvolumes:\n  pg-phoenix:\n  phoenix-data:\n``` |
| **OTLP endpoint for app** | `http://otel-collector:4318/v1/traces` — same OTel collector; collector forwards to Phoenix via OTLP HTTP exporter at `phoenix:6006/v1/traces` (Phoenix accepts OTLP on `/v1/traces`). |
| **Resource footprint** | **Low–Medium**: 2 containers (Phoenix + Postgres). SQLite mode is even lighter (1 container, no Postgres). Phoenix on SQLite uses ~200–500 MB RAM; on Postgres ~1–2 GB RAM. CPU: 1–2 cores. Suitable for CI and laptops. |
| **How traces appear** | Web UI at `http://localhost:6006`. Trace waterfall, span table, LLM-specific views (prompt/response, token usage, latency), evaluations, datasets, experiments, prompt playground. |
| **Prompt/response content** | ✅ Yes — captures full prompt, response, token counts, model params, latency. "Trace inspector" shows raw JSON. Built-in LLM evals (correctness, hallucination, etc.). |
| **Content-capture switch** | Works natively. Phoenix respects `PHOENIX_COLLECTOR_ENDPOINT` and `PHOENIX_CLIENT_HEADERS`. The repo's redaction blocklist can be applied in the OTel collector's `attributes` processor before export, or via Phoenix's `PHOENIX_REDACT_KEYS` (if supported; check version). |
| **Python deps / migration friction** | **Medium friction**: Requires `arize-phoenix` Python SDK (`pip install arize-phoenix`) or use OTel native (`opentelemetry-sdk`, `opentelemetry-exporter-otlp`). The repo already uses OTel-native concepts (OTLP endpoint in config). A `PhoenixTracingAdapter` would wrap the SDK's `PhoenixTracer` or use OTel directly. Existing `TracingPort` contract tests stay valid. Less invasive than Langfuse because Phoenix is OTLP-first. |
| **Repo-specific notes** | - Adds only 2 services to `docker-compose.test.yml` (or reuses existing `postgres` with a different DB name).<br>- Phoenix on SQLite is zero-config for local dev — no Postgres needed if persistence isn't required across restarts.<br>- License: **Elastic License 2.0** (source-available, not OSI-approved). This may conflict with repo's "zero paid services" + open-source norm.<br>- Phoenix is single-tenant; multi-team needs separate instances.<br>- Migration path: Keep `TracingAdapter`, add a `PhoenixBackend` that implements `add_span` using `phoenix.trace()` or OTel exporter. |

---

## 3. Grafana Stack (Tempo + Loki + Grafana)

| Aspect | Details |
|--------|---------|
| **docker-compose snippet** | ```yaml\nservices:\n  tempo:\n    image: grafana/tempo:2.5\n    command: ["-config.file=/etc/tempo.yaml"]\n    volumes:\n      - ./infra/tempo/tempo.yaml:/etc/tempo.yaml\n      - tempo-data:/var/tempo\n    ports:\n      - "3200:3200"   # Tempo HTTP\n      - "4317:4317"   # OTLP gRPC (optional, collector already has)\n      - "4318:4318"   # OTLP HTTP\n  loki:\n    image: grafana/loki:3.1\n    command: ["-config.file=/etc/loki.yaml"]\n    volumes:\n      - ./infra/loki/loki.yaml:/etc/loki.yaml\n      - loki-data:/loki\n    ports:\n      - "3100:3100"\n  grafana:\n    image: grafana/grafana:11.1\n    volumes:\n      - ./infra/grafana/datasources.yaml:/etc/grafana/provisioning/datasources/datasources.yaml\n      - ./infra/grafana/dashboards:/etc/grafana/provisioning/dashboards\n      - grafana-data:/var/lib/grafana\n    ports:\n      - "3000:3000"\n    environment:\n      - GF_AUTH_ANONYMOUS_ENABLED=true\n      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin\n    depends_on:\n      - tempo\n      - loki\n  otel-collector:\n    image: otel/opentelemetry-collector-contrib:0.120.0\n    volumes:\n      - ./infra/otel/collector.yaml:/etc/otelcol-contrib/config.yaml\n    ports:\n      - "4317:4317"\n      - "4318:4318"\n      - "8888:8888"\n    depends_on:\n      - tempo\n      - loki\nvolumes:\n  tempo-data:\n  loki-data:\n  grafana-data:\n``` |
| **OTLP endpoint for app** | `http://otel-collector:4318/v1/traces` — existing OTel collector (already in `docker-compose.test.yml`) forwards traces to Tempo (`tempo:4317` via OTLP gRPC) and logs to Loki. |
| **Resource footprint** | **Medium**: 4 containers (Tempo, Loki, Grafana, OTel collector). Tempo ~1–2 GB RAM, Loki ~500 MB, Grafana ~200 MB, Collector ~200 MB. Total ~2–3 GB RAM. Higher than Phoenix, lower than Langfuse. |
| **How traces appear** | Grafana Explore at `http://localhost:3000`. TraceQL queries, trace waterfall, span details, log correlation (Loki), metrics (Prometheus — already in infra). No LLM-specific views (no prompt playground, no evals UI). |
| **Prompt/response content** | ⚠️ **Partial** — Tempo stores span attributes. If the app emits `llm.prompt` / `llm.response` as span attributes (via OTel semantic conventions), they appear in span details. But: no dedicated LLM trace UI, no token usage charts, no evals. Requires custom Grafana dashboards. |
| **Content-capture switch** | Works if the OTel collector's `attributes` processor redacts `SENSITIVE_SPAN_FIELDS` before export. The repo's `_tracing_redaction.py` blocklist can be mirrored in collector config. |
| **Python deps / migration friction** | **Low friction**: The repo already uses OTel collector and OTLP endpoint config. No new Python SDK needed — just ensure spans emit OTel semantic attributes (`gen_ai.prompt`, `gen_ai.completion`, `gen_ai.usage.*`). The existing `TracingAdapter` + `record_tracing_backend_span` can stay; the backend becomes the OTel collector (already wired). Only change: update `infra/otel/collector.yaml` to export to Tempo/Loki. |
| **Repo-specific notes** | - **Already have Prometheus + Grafana in infra** (per issue #271 context). Tempo + Loki extend the existing stack.<br>- Reuses existing `otel-collector` service from `docker-compose.test.yml` (just update its config).<br>- No new Python dependencies.<br>- Migration: **Non-breaking** — current in-memory spans (`_spans` list) can remain for tests; production path goes through OTel collector.<br>- Need to write `tempo.yaml`, `loki.yaml`, `grafana/datasources.yaml`, and update `collector.yaml` with `otlp` exporters to Tempo/Loki.<br>- TraceQL is powerful but has a learning curve; no "prompt playground" out of the box. |

---

## 4. Plain OTLP Collector (file/JSON output)

| Aspect | Details |
|--------|---------|
| **docker-compose snippet** | ```yaml\nservices:\n  otel-collector:\n    image: otel/opentelemetry-collector-contrib:0.120.0\n    volumes:\n      - ./infra/otel/collector.yaml:/etc/otelcol-contrib/config.yaml\n      - otel-data:/data\n    ports:\n      - "4317:4317"\n      - "4318:4318"\n      - "8888:8888"\nvolumes:\n  otel-data:\n``` |
| **OTLP endpoint for app** | `http://otel-collector:4318/v1/traces` — unchanged from current `config/dev.yaml` (`otlp_endpoint: ""` defaults to collector). |
| **Resource footprint** | **Minimal**: 1 container (~100–200 MB RAM, <0.5 CPU). Already running in `make docker-up`. |
| **How traces appear** | **File/JSON** at `/data/telemetry.json` (or stdout via `debug` exporter). No UI. Inspect with `jq`, `less`, or import into Jaeger/Zipkin locally. |
| **Prompt/response content** | ✅ Yes — if the app emits `gen_ai.prompt` / `gen_ai.completion` as span attributes, they are in the JSON. But: no search, no waterfall, no correlation. Manual inspection only. |
| **Content-capture switch** | Works — the collector's `attributes` processor can redact `SENSITIVE_SPAN_FIELDS` before writing to file. |
| **Python deps / migration friction** | **Zero friction**: No code changes. Current `TracingAdapter` + `record_tracing_backend_span` (no-op) stays. The OTel collector already receives spans from the app (if `otlp_endpoint` is set). Just update `collector.yaml` to add `file` exporter. |
| **Repo-specific notes** | - **Already the status quo** — `infra/otel/collector.yaml` has `debug` exporter only. Adding `file` exporter is a 5-line change.<br>- Use `fileexporter` (contrib) with `path: /data/telemetry.json`, `rotation` config.<br>- For local inspection: `docker compose exec otel-collector cat /data/telemetry.json | jq .`<br>- **Not a "viewer"** — fails the "trace UI" requirement. Only viable as a stopgap or for CI artifact collection. |

---

## Comparison Table

| Criterion | Langfuse OSS | Arize Phoenix | Grafana Stack (Tempo/Loki/Grafana) | Plain OTLP Collector |
|-----------|--------------|---------------|-----------------------------------|----------------------|
| **Docker services added** | +6 (web, worker, pg, ch, redis, minio) | +2 (phoenix, pg) or +1 (SQLite) | +3 (tempo, loki, grafana) — collector exists | 0 (collector exists) |
| **RAM (approx)** | 3–5 GB | 0.5–2 GB | 2–3 GB | 0.1–0.2 GB |
| **CPU cores** | 4+ | 1–2 | 2–3 | <1 |
| **CI-friendly** | ❌ No (too heavy) | ✅ Yes (SQLite mode) | ⚠️ Marginal (3+ services) | ✅ Yes |
| **Trace UI** | ✅ Full LLM-native (playground, evals, prompts) | ✅ Full LLM-native (playground, evals, prompts) | ⚠️ Generic (TraceQL, no LLM views) | ❌ None (JSON file) |
| **Prompt/response capture** | ✅ Native | ✅ Native | ✅ Via OTel attributes (manual) | ✅ Via OTel attributes (manual) |
| **Content-capture switch** | ✅ Native redaction config | ✅ Native / collector processor | ✅ Collector processor | ✅ Collector processor |
| **Python deps required** | `langfuse` SDK (new) | `arize-phoenix` SDK or OTel native | None (OTel native) | None |
| **Migration from in-memory spans** | Breaking (new backend) | Medium (new backend or OTel) | Non-breaking (OTel collector path) | Non-breaking (no change) |
| **License** | MIT (OSI) | Elastic 2.0 (source-available, not OSI) | AGPLv3 (Grafana), Apache 2.0 (Tempo/Loki) | Apache 2.0 |
| **Repo norm fit (docker-compose, zero paid, OTel-native)** | ⚠️ Heavy, not OTel-first (has SDK) | ⚠️ License concern, OTel-native | ✅ OTel-native, extends existing Grafana/Prom | ✅ OTel-native, zero change |
| **Local dev ergonomics** | Excellent UI, heavy stack | Excellent UI, light stack | Good UI, generic, needs dashboards | Poor (manual JSON) |
| **Evals / prompt playground** | ✅ Built-in | ✅ Built-in | ❌ Custom dashboards only | ❌ None |

---

## Recommendation: **Arize Phoenix (SQLite mode) for local dev**

### Rationale

1. **Fits repo norms best**:
   - Docker-compose: adds only 1–2 services (Phoenix + optional Postgres). SQLite mode = 1 container.
   - Zero paid services: fully self-hosted, no cloud dependency.
   - OTel-native: accepts OTLP directly; the repo's existing `otlp_endpoint` config and OTel collector work unchanged.
   - `make docker-up` already runs OTel collector; Phoenix just consumes from it.

2. **Resource footprint**: Lowest among UI options. SQLite mode runs in ~200 MB RAM, suitable for CI and laptops.

3. **LLM-native UI**: Prompt/response capture, token usage, latency, evals, datasets, prompt playground — all built-in. Matches the "content-capture switch" requirement exactly.

4. **Migration path**:
   - Keep `TracingAdapter` and `TracingPort` contract tests.
   - Add a `PhoenixBackend` that implements `add_span` using `phoenix.trace()` or configure the OTel collector to export to Phoenix (`exporters.otlp.endpoint: phoenix:6006/v1/traces`).
   - No Python SDK required if using OTel collector → Phoenix path (recommended).
   - In-memory spans (`_spans` list) remain for unit tests; production path goes through collector.

5. **License caveat**: Elastic License 2.0 is source-available, not OSI-approved. If this is a blocker, **Grafana Stack** is the fallback (Apache 2.0 / AGPLv3), but requires building LLM-specific dashboards and has higher resource cost.

### Integration Sketch (Phoenix + OTel Collector)

**docker-compose.test.yml additions:**
```yaml
services:
  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    environment:
      - PHOENIX_WORKING_DIR=/mnt/data
      - PHOENIX_SQL_DATABASE_URL=sqlite:///mnt/data/phoenix.db  # SQLite for local dev
    volumes:
      - phoenix-data:/mnt/data
    depends_on:
      - otel-collector

volumes:
  phoenix-data:
```

**infra/otel/collector.yaml (extend existing):**
```yaml
exporters:
  debug:
    verbosity: basic
  otlp/phoenix:
    endpoint: "phoenix:6006/v1/traces"
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, attributes/redact]
      exporters: [debug, otlp/phoenix]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]

processors:
  attributes/redact:
    actions:
      - key: "question"
        action: delete
      - key: "chunk_text"
        action: delete
      - key: "answer"
        action: delete
      - key: "pii"
        action: delete
      - key: "credentials"
        action: delete
      - key: "signed_url"
        action: delete
```

**config/dev.yaml:**
```yaml
observability:
  otlp_endpoint: "http://localhost:4318/v1/traces"
  # ... rest unchanged
```

**No Python code changes** — the app sends to OTel collector, collector forwards to Phoenix.

---

## Next Steps

1. **Prototype**: Add Phoenix service to `docker-compose.test.yml` and update `collector.yaml` (30 min).
2. **Verify**: Run `make docker-up`, send a test trace, confirm it appears in `http://localhost:6006`.
3. **Contract test**: Ensure `tests/contract/test_tracing_contract.py` passes with the new backend.
4. **Document**: Add `docs/adr/0005-local-trace-viewer.md` with the decision.
5. **Comment on #267**: Link this research doc and the prototype branch.

---

*Research compiled for issue #267. Push to `research/local-trace-viewer` branch with context pointer.*
