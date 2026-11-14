# AWS Infra, Code Push & CI/CD Plan

**Status:** Approved, ready for implementation
**Date:** 2026-11-14
**Scope:** Get Phase 1 code onto `main`, stand up AWS infrastructure, and run CI/CD before starting Phase 2
**Out of scope:** Web UI features (Phase 2), staging/dev AWS environments (defined in code, not deployed)

---

## 1. Decisions on record

| Decision | Choice |
| --- | --- |
| Code push | One PR: `research/local-trace-viewer` (365 Phase 1 commits) → `main`, CI-validated |
| AWS | Single account, `us-east-1`, deploy the `prod` CDK environment only |
| CI/CD | Auto-deploy on merge to `main`; production approval gate defined but disabled for now |
| Database | `vector_store` switch: `neon_pgvector` (pilot default) / `aurora_pgvector` (standard path, in code, off) |
| Secrets | `secrets.provider` switch: `parameter_store` (pilot default) / `secrets_manager` (standard path) |
| Observability | `observability.backend` switch: `cloudwatch` (pilot default) / `otlp_endpoint` (standard path) |
| API | Keep API Gateway HTTP API (usage-priced, no fixed floor) + custom domain `finsight.sahcreatives.com` |
| Frontend | Next.js in `web/` → Vercel Hobby (free), deploy from Phase 2 onward |
| Local | `test` and `development` environments stay on localhost (docker compose / LocalStack) |

## 2. Budget (target: minimal fixed monthly cost)

| Component | Monthly |
| --- | --- |
| Neon (free plan) | $0 |
| Lambda / DynamoDB / SQS / Step Functions / Cognito / SSM | $0 (free tiers) |
| S3 | < $0.50 |
| API Gateway HTTP API | ~$0–1 (usage-priced) |
| CloudWatch (≤3 dashboards, ≤10 alarms, 30-day log retention) | ~$1–3 |
| Vercel Hobby | $0 |
| **Total** | **~$2–5/mo** |

Design rules that keep this low:

- **No NAT gateway.** Lambda reaches S3/DynamoDB via free gateway VPC endpoints.
- **No Aurora while the switch is off.** Aurora Serverless v2 has a ~$44/mo floor; the CDK stack stays in code but undeployed.
- **SSM Parameter Store over Secrets Manager** while the pilot value is active.
- **Log retention capped at 30 days** everywhere.
- **Single-AZ, on-demand billing** for everything.

## 3. Guardrails

- **Billing alarm: $5/month default, configurable — never hard-coded.** The budget amount is a config value (`infra.cdk.config.envs.yaml` → `alerts.monthly_budget_usd`), so it can be raised or lowered by config change (PR) as spending patterns evolve. Default starts at $5.
- **Cost Explorer anomaly detection** on (free).
- **Neon free plan checks** (per-project limits as of 2026-10): **1 GB Postgres storage**, **2 CU max compute (≈8 GB RAM)**, **5 GB network transfer/month**, 100 CU-hours/month (scale-to-zero after 5 min idle, not disableable). Exceeding storage or transfer makes *writes fail* (data is not deleted). A CloudWatch-side metric check warns before the storage cap.

## 4. New config switches (all follow the binding switch rules)

Both paths written and tested. Unknown values fail startup loudly. Active values logged at startup and tagged on traces. CI runs the golden set on both pilot and standard configs.

| Switch | Pilot (default) | Standard path | Notes |
| --- | --- | --- | --- |
| `vector_store` | `neon_pgvector` | `aurora_pgvector` | Aurora adapter already exists; CDK stack stays undeployed. Flip later = config PR + data migration (`pg_dump`/`pg_restore`) |
| `secrets.provider` | `parameter_store` | `secrets_manager` | Resolution layer in `core/config` (the one place allowed to touch AWS). LocalStack supports both paths for integration tests |
| `observability.backend` | `cloudwatch` | `otlp_endpoint` | Generic OTLP path = same exporter, different endpoint/headers from config. Provider switch, never an on/off switch |

## 5. Stages

### Stage A — Code onto `main`

1. `make preflight` baseline gate (binding)
2. Commit the 2 pending config changes (`config/schema.yaml`, `config/test.yaml`)
3. Merge the 1-commit drift on `origin/main` (GitHub Actions bump)
4. Open one PR `research/local-trace-viewer` → `main`; confirm CI green; merge
5. Verify branch protection ruleset on `main` (required: `Summary`, pre-commit, Infra Synth)

### Stage B — AWS plumbing (human-in-console steps)

1. Configure AWS CLI + credentials; billing budget alarm ($5/mo default, from config) + anomaly alerts
2. GitHub OIDC identity provider + IAM deploy role for `prod`
3. GitHub Environments (`dev`, `staging`, `production`); `AWS_ROLE_ARN` + `AWS_REGION` as environment vars
4. Owner creates the Neon account + project; connection string stored in SSM Parameter Store
5. `cdk bootstrap` the account

### Stage C — Code changes (binding pre-flight: baseline → failing test → implement → architecture test → green commit)

1. `vector_store` switch extension + Neon pgvector adapter (`vector_store/neon_pgvector`)
2. `secrets.provider` switch + SSM / Secrets Manager resolution layer
3. `observability.backend` switch + generic OTLP path
4. CDK lean stack: Aurora behind the switch (undeployed), no NAT, SSM wiring, per-function IAM, 30-day log retention
5. Observability stacks: CloudWatch dashboard, alarms, Neon storage metric check
6. API Gateway + custom domain mapping (`finsight.sahcreatives.com`), ACM cert (`us-east-1`), throttling from config
7. Billing budget as configurable value (`alerts.monthly_budget_usd` in CDK env config), default $5

### Stage D — Deploy workflow (closes DI-22)

- `deploy.yml` (backend only): on merge to `main` → OIDC assume role → `make lambda-build` (vendored runtime deps) → `cdk deploy` (prod) → `alembic upgrade head` against Neon → smoke tests (health endpoint + one read-only check)
- Tag/release workflow with notes + artifacts
- Frontend deploys via Vercel GitHub integration (separate, free) — Phase 2
- Update `docs/deployment.md` and `docs/runbook.md`: remove scaffolding caveats, document rollback (redeploy previous Lambda version; Neon restore path)

### Stage E — First deploy & verify

1. Deploy; run smoke tests
2. Attach the custom domain; confirm HTTPS
3. Exercise rollback once (redeploy previous version)
4. Confirm alarms + dashboard live; confirm traces and token-cost metrics flowing (continues the #286–289 observability work)

## 6. Verification checklist

- [ ] `main` up to date with all Phase 1 work; branch protection enforced
- [ ] `prod` CDK environment deployed; `finsight.sahcreatives.com` serves the API
- [ ] Auto-deploy on merge works end to end; smoke tests pass on the deployed environment
- [ ] All three switches validate both paths in CI; unknown values refuse startup
- [ ] Billing alarm fires a test alert; monthly spend tracking visible in Cost Explorer
- [ ] Dashboard + alarms live; OTLP traces visible in CloudWatch Logs
