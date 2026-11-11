# Research: AWS-Native Trace & Alarm Path (Issue #271)

**Date:** 2026-11-11
**Status:** Research complete — decision matrix and recommendation below.

---

## Executive Summary

This research evaluates how OTLP spans from the FinSight AI Lambda functions reach AWS observability services, and which path best aligns with:
- Existing CDK/IaC scaffolding (ADR-0002, DI-20–22)
- The five synthesized CloudWatch alarms in `observability.py`
- The config loader's fail-loudly behavior (`loader.py`)
- The current Lambda packaging gap (DI-21, no third-party deps vendored)

**Recommendation: Option B (OTLP → CloudWatch Logs native ingestion)**

Option B is the path of least resistance. It:
- Uses the existing metric filters in `observability.py` **exactly as written** (they match `$.span.attributes.*` JSON log fields)
- Requires only CDK changes: enable CloudWatch OTLP endpoint + IAM role for SigV4 + Lambda env vars
- Avoids ADOT Lambda layer operational complexity (Option A)
- Avoids self-hosted Tempo burden (Option D)
- Aligns with "zero paid services" constraint (CloudWatch Logs OTLP ingestion is included)

---

## Decision Matrix

| Dimension | Option A: ADOT Lambda Layer → X-Ray | **Option B: OTLP → CloudWatch Logs (Recommended)** | Option D: Self-Hosted Grafana Tempo |
|-----------|-------------------------------------|---------------------------------------------------|-------------------------------------|
| **CDK Changes** | Add layer ARN, `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler`, X-Ray exporter config | Enable CloudWatch OTLP endpoint, add IAM role with `logs:PutLogEvents` + SigV4, set `OTLP_ENDPOINT` env var | Deploy Tempo on ECS/EC2, add data source to Grafana (not in CDK yet) |
| **IAM** | Lambda role needs `xray:PutTraceSegments`, `xray:PutTelemetryRecords` | Lambda role needs `logs:PutLogEvents` on the log group + SigV4 signing (via `aws:SourceArn` condition) | Tempo needs persistent storage (EBS/EFS), network config, auth |
| **Cost** | X-Ray traces: $5M traces free, then $5/M traces + data scan | CloudWatch Logs: $0.50/GB ingested, $0.03/GB archived; metric filters ~$0.30/metric/month | EC2/ECS compute + storage + Grafana (paid or self-hosted) — **violates "zero paid services"** |
| **Operational Burden** | ADOT layer version pinning, X-Ray sampling config, segment size limits | Native AWS service, no sidecar/layer, GA since 2024, auto-scales | Full ops ownership: upgrades, backups, scaling, HA, security patches |
| **Alarm Compatibility** | ❌ **Breaks existing alarms** — metric filters on `$.span.attributes.*` don't match X-Ray segment schema. Would need CloudWatch metric math on X-Ray traces or X-Ray Insights alarms (different design, new CDK). | ✅ **Matches existing alarms exactly** — `observability.py` filters `$.span.attributes.fallback_3_used`, `$.span.attributes.embedding_retries`, etc. work on JSON log events as-is. | ❌ Requires new alarm design — Tempo metrics via PromQL/Grafana, not CloudWatch metric filters |
| **Lambda Env-Var Delivery** | Needs `OTEL_EXPORTER_OTLP_ENDPOINT` (X-Ray), `AWS_LAMBDA_EXEC_WRAPPER`, layer ARN | Needs `OTLP_ENDPOINT=https://logs.{region}.amazonaws.com/v1/logs`, `ENVIRONMENT=production`, SigV4 creds via IAM role | Needs `OTLP_ENDPOINT` pointing to Tempo, auth headers |
| **Dep Vendoring (DI-21)** | ADOT layer includes OTel SDK — **but** layer ARN must be maintained per region/arch; app still needs `opentelemetry-*` for manual instrumentation | App must vendor `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-*` (already in `pyproject.toml`). `build_lambda.py` must vendor them (DI-21). | Same as Option B — app vendors OTel SDK |
| **Local/Dev Parity** | ADOT layer not available locally; LocalStack X-Ray support limited | CloudWatch OTLP endpoint not in LocalStack; use OTel Collector (already in `infra/otel/collector.yaml`) for dev | Tempo can run in docker-compose for dev parity |
| **Maturity** | ADOT Lambda layer GA, but X-Ray has 64KB segment limit, sampling gotchas | CloudWatch OTLP ingestion GA 2024, purpose-built for Lambda logs+traces | Tempo mature, but self-hosted = you own it |

---

## Detailed Findings

### 1. How OTLP Spans Reach AWS (CDK/IaC Context)

**Current State:**
- `infra/cdk/app/app.py` synthesizes 6 stacks (Network, Data, Messaging, Auth, StepFunctions, Compute, Observability)
- `ObservabilityStack` creates:
  - CloudWatch Log Group: `/aws/lambda/finsight-{env}`
  - 5 metric filters + alarms on structured JSON fields (see `observability.py:143-280`)
- `ComputeStack` creates Lambda with **zero environment variables** (see `compute.py:63-77`)
- `loader.py` fails loudly on unresolved `${VAR}` (line 92-95) — `OTLP_ENDPOINT` **must** be set in Lambda env
- `build_lambda.py` docstring: "Third-party dependencies are not vendored yet; that remains part of DI-21" (line 5-6)

**ADR-0002** (Infrastructure as Code):
- CDK in Python, parameterized from `infra/cdk/config/envs.yaml`
- CI runs `make infra-synth` (non-deploying)
- Deploys use GitHub OIDC (deferred, DI-22)
- Secrets from Secrets Manager/SSM, never committed

**DI-20, DI-21, DI-22** — **Explicitly not implemented** (dev-infra plan, section 17):
- DI-20: CloudWatch dashboards/alarms — scaffolded in `observability.py` but not deployed
- DI-21: Lambda packaging + dep vendoring — `build_lambda.py` exists but vendors **zero** third-party deps
- DI-22: Deploy workflow via GitHub OIDC — deferred

**Conclusion:** Nothing is fixed. This ticket **is** the design that DI-20/21 will implement.

---

### 2. Lambda Env-Var Delivery

`compute.py` sets **no** `environment` dict on the Lambda function (lines 63-77). The `lambda_kwargs` only passes `vpc` and `code`.

**Required env vars for Option B:**
```python
environment = {
    "OTLP_ENDPOINT": f"https://logs.{region}.amazonaws.com/v1/logs",
    "ENVIRONMENT": env_name,  # "production" | "staging" | "dev"
    "AWS_REGION": region,
    # Secrets (via Secrets Manager/SSM, DI-21):
    # "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer <sigv4-token>"  # or use IAM auth
}
```

**Loader behavior (`loader.py:71-98`):**
- `${OTLP_ENDPOINT}` in config → resolved from Lambda env var
- Fails loudly if missing (except in `test` env where it returns `test-otlp-endpoint`)
- `prod.yaml:69` has `otlp_endpoint: "${OTLP_ENDPOINT}"` — **will fail at startup if not set**

---

### 3. Five Alarms — Metric Filters vs Real Log Shape

`observability.py` defines 5 metric filters with patterns matching **both** top-level JSON fields and `$.span.attributes.*`:

| Alarm | Filter Pattern (excerpt) | Metric Value |
|-------|--------------------------|--------------|
| `fallback_model_3_used` | `{ ($.fallback_3_used = true) \|\| ($.span.attributes.fallback_3_used = true) }` | `'1'` |
| `reranker_down` | `{ ($.reranker_down = true) \|\| ($.alert = "reranker_down") \|\| ($.span.attributes.reranker_down = true) \|\| ($.span.attributes.alert = "reranker_down") }` | `'1'` |
| `embedding_retries_exceeded` | `{ ($.embedding_retries >= 1) \|\| ($.span.attributes.embedding_retries >= 1) }` | `'$.embedding_retries'` |
| `job_in_retry_list` | `{ ($.job_in_retry_list = true) \|\| ($.span.attributes.job_in_retry_list = true) }` | `'1'` |
| `role_cache_stale_seconds` | `{ ($.role_cache_stale_seconds >= 1) \|\| ($.span.attributes.role_cache_stale_seconds >= 1) }` | `'$.role_cache_stale_seconds'` |

**Critical insight:** The patterns **already match `$.span.attributes.*`** — this is the exact JSON shape produced when OTLP spans are ingested via CloudWatch Logs native OTLP endpoint (each span becomes a structured log event with `span.attributes` map).

**Option B compatibility:** ✅ **Perfect match** — no alarm changes needed.

**Option A (X-Ray) incompatibility:** ❌ X-Ray segments have different schema (`segments`, `subsegments`, `annotations`, `metadata`). Metric filters on `$.span.attributes.*` would **never match**. Would need:
- CloudWatch metric math on X-Ray trace data, OR
- X-Ray Insights alarms (separate product, different CDK constructs)

---

### 4. Dep-Vendoring Prerequisite (DI-21)

`pyproject.toml` already declares runtime dependencies:
```toml
"opentelemetry-api>=1.28.0,<2",
"opentelemetry-sdk>=1.28.0,<2",
"opentelemetry-exporter-otlp>=1.28.0,<2",
"opentelemetry-instrumentation-fastapi>=0.48b0,<1",
"opentelemetry-instrumentation-sqlalchemy>=0.48b0,<1",
"opentelemetry-instrumentation-httpx>=0.48b0,<1",
```

`build_lambda.py` currently bundles only `src/finsight` and `config/` (line 18). **No third-party deps.**

**Required for Option B:**
- `build_lambda.py` must vendor all `opentelemetry-*` packages + transitive deps (`protobuf`, `googleapis-common-protos`, etc.)
- Or use a Lambda Layer for heavy deps (but ADOT layer is Option A; for Option B, a custom layer with OTel SDK is viable)
- DI-21 explicitly tracks this: "Third-party dependencies are not vendored yet; that remains part of DI-21"

---

## Recommendation: Option B (OTLP → CloudWatch Logs)

### Why Option B Wins

1. **Alarm compatibility** — The 5 synthesized alarms in `observability.py` work **as written** with zero changes.
2. **Lowest operational burden** — No ADOT layer version pinning, no X-Ray sampling tuning, no self-hosted infra.
3. **Native AWS service** — CloudWatch Logs OTLP ingestion is GA (2024), purpose-built for Lambda.
4. **Cost-effective** — Pay per GB ingested; no X-Ray trace charges beyond free tier.
5. **Aligns with config loader** — `OTLP_ENDPOINT` env var maps directly to `observability.otlp_endpoint` in config.
6. **Future-proof** — CloudWatch Logs is the long-term home for structured logs + spans in AWS.

### Concrete Next Steps (Implementation Order)

| Step | Action | File(s) | Gate |
|------|--------|---------|------|
| 1 | **Add OTel SDK vendoring to `build_lambda.py`** (DI-21) | `scripts/build_lambda.py` | `make preflight` passes, zip contains `opentelemetry/` |
| 2 | **Add Lambda environment variables in `ComputeStack`** | `infra/cdk/stacks/compute.py` | Synth shows `environment` dict with `OTLP_ENDPOINT`, `ENVIRONMENT` |
| 3 | **Grant Lambda IAM role `logs:PutLogEvents` on the Observability log group** | `infra/cdk/stacks/compute.py` + `observability.py` | IAM policy in synthesized template |
| 4 | **Enable CloudWatch OTLP endpoint** (account-level, one-time) | AWS Console / CDK `CfnResource` for `AWS::Logs::Delivery` | `aws logs describe-deliveries` shows OTLP delivery |
| 5 | **Wire `OTLP_ENDPOINT` from Secrets Manager/SSM** (DI-21 secrets wiring) | `infra/cdk/stacks/compute.py`, `infra/cdk/config/envs.yaml` | No hardcoded endpoints in CDK |
| 6 | **Verify metric filters fire** — deploy to `dev`, invoke Lambda, check CloudWatch metrics | — | Alarms show `OK` with sample data |
| 7 | **Add CloudWatch Dashboard** (DI-20) | `infra/cdk/stacks/observability.py` | Dashboard visible in console |

### CDK Changes Required (Option B)

**`compute.py` — Add environment + IAM:**
```python
# In ComputeStack.__init__, after role creation:
from aws_cdk import aws_logs as logs

# ... existing role code ...

# Grant PutLogEvents on the Observability log group (passed in or looked up)
log_group_arn = f"arn:aws:logs:{region}:{account}:log-group:/aws/lambda/finsight-{env_name}:*"
role.add_to_policy(iam.PolicyStatement(
    actions=["logs:PutLogEvents"],
    resources=[log_group_arn],
    conditions={"StringEquals": {"aws:SourceArn": f"arn:aws:lambda:{region}:{account}:function:finsight-{env_name}-api"}}
))

# Lambda environment
self.api_fn = lambda_.Function(
    # ... existing args ...
    environment={
        "OTLP_ENDPOINT": f"https://logs.{region}.amazonaws.com/v1/logs",
        "ENVIRONMENT": env_name,
        "AWS_REGION": region,
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",  # CloudWatch OTLP uses HTTP/protobuf
        "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "true",
    },
    # ... rest ...
)
```

**`observability.py` — No changes needed** (alarms already match `$.span.attributes.*`).

**`app.py` — Pass log group reference to ComputeStack:**
```python
obs = ObservabilityStack(app, f'FinSight-{env_name}-Observability', env=env, env_name=env_name)
ComputeStack(
    # ... existing args ...
    observability=obs,  # pass log group reference
)
```

---

## Rejected Options

### Option A: ADOT Lambda Layer → X-Ray
- **Blocker:** Existing 5 alarms in `observability.py` **cannot work** with X-Ray segment schema without redesign.
- **Operational cost:** ADOT layer version management per region/architecture, X-Ray 64KB segment limit, sampling configuration.
- **Only viable if:** Team commits to X-Ray as primary tracing UI and accepts alarm redesign.

### Option C: ADOT Collector Sidecar/ECS Task
- **Not Lambda-native** — requires ECS/Fargate or EC2. Skip unless migrating off Lambda.

### Option D: Self-Hosted Grafana Tempo
- **Violates "zero paid services"** — requires compute, storage, ops ownership.
- **Alarm incompatibility** — would need Grafana Alerting + PromQL, not CloudWatch metric filters.
- **Only viable if:** Team already runs Tempo/Grafana stack and wants unified observability.

---

## Appendix: Current Code References

| Component | File | Key Lines |
|-----------|------|-----------|
| Observability Stack (alarms) | `infra/cdk/stacks/observability.py` | 1-280 |
| Compute Stack (Lambda, no env) | `infra/cdk/stacks/compute.py` | 63-77 |
| Config Loader (fail-loudly) | `src/finsight/core/config/loader.py` | 71-98 |
| Lambda Packaging (no deps) | `scripts/build_lambda.py` | 5-6, 18 |
| ADR-0002 (CDK decision) | `docs/adr/0002-infrastructure-as-code.md` | 1-23 |
| Dev-Infra Plan (DI-20/21/22) | `docs/plans/archive/dev-infra-implementation-plan.md` | 841-985 |
| Tracing Adapter (OTel SDK) | `src/finsight/adapters/tracing/tracing_adapter.py` | 72-79 |
| Schema (observability config) | `config/schema.yaml` | 246-258 |

---

## Push to Throwaway Branch

```bash
git checkout -b research/aws-trace-path
git add research/aws-trace-path.md
git commit -m "research: AWS-native trace & alarm path decision matrix (issue #271)

Option B (OTLP -> CloudWatch Logs) recommended.
Existing alarms in observability.py match span.attributes JSON shape exactly.
Requires: build_lambda.py vendoring (DI-21), Lambda env vars in ComputeStack,
IAM logs:PutLogEvents, CloudWatch OTLP endpoint enablement.
"
git push origin research/aws-trace-path
```

**Context pointer on Issue #271:** This research document provides the decision matrix and concrete next steps for implementing the AWS-native trace & alarm path. The recommended Option B aligns with existing CDK alarm scaffolding, config loader behavior, and the DI-21 vendoring prerequisite.
