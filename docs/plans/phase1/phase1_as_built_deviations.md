# Phase 1 As-Built Deviations Addendum

**Status:** As-built truth for Phase 1, verified against the repository on 2026-11-21.
**Tickets:** #350 (this addendum), child of #345 (Phase 2 spec).
**Parent plans (authoritative for scope and architecture):** `docs/plans/project_requirement/finsightAI.md`, `docs/plans/architecture/phase1/finsight_mvp_hld.svg`, `docs/plans/phase1/phase1_mvp_plan.md`, and the binding `docs/plans/project_requirement/finsight_config_switches.md` and `docs/plans/aws-infra-cicd-plan.md`.

## 1. Purpose and precedence

The parent plans remain authoritative for **scope and architecture**, and the binding Mandatory Policies in `AGENTS.md` still govern all implementation work. They are not edited by this addendum. This addendum records where the **implemented Phase 1 system actually differs** from those plans; it is the source of truth for what the current baseline is. It does not license disregarding a binding rule: if a parent plan, the Config Switch Guide, an ADR, a UI standard and the code disagree, **stop and escalate** before changing behaviour, as `AGENTS.md` requires. Do not silently "fix" the code back to older plan text, and do not treat a documented deviation as permission to breach a binding policy.

Every entry below is backed by a file:line citation. Where a plan statement and the as-built code conflict, both are shown. Deployment claims are about what the repository's workflow, CDK config and deployment records show, not an independent AWS console audit.

Related records: ADR-0002 (IaC), ADR-0004 (document lifecycle), ADR-0005 (LLM content capture), ADR-0006 (OTLP to CloudWatch), ADR-0007 (span schema), `docs/plans/phase1/phase1_reconciliation.md`, `docs/deployment.md`, `docs/runbook.md`.

---

## 2. Document lifecycle and the upload form (`upload_types`)

**Deviation:** `upload_types` is only `new` / `update`. There is no `delete` control in the upload form; delete, restore and permanent purge are document-library actions.

- Accepted ADR-0004 removes `delete` from upload and moves delete/restore/purge to the document library and recycle bin: `docs/adr/0004-document-lifecycle-separation.md:24-38`, `:42-50`.
- The Phase 1 plan already reflects this: `docs/plans/phase1/phase1_mvp_plan.md:144`, `:156`, `:180`, `:223`. The HLD upload form likewise lists "Category, upload type (New, Update), draft or final": `docs/plans/architecture/phase1/finsight_mvp_hld.svg:79`.
- Binding config rule: `upload_types` must be exactly `new` and `update` — `docs/plans/project_requirement/finsight_config_switches.md:115`, `:291`. As-built config matches: `config/schema.yaml:299`, `config/test.yaml:233`.
- API constant and rejection of any other value: `src/finsight/entrypoints/api/upload.py:82`, `:599-605`.
- UI allows only the configured types (falling back to `new`/`update`), shows category, period, status, replacement target and file picker, and renders no delete control: `web/src/app/(app)/upload/upload-form.tsx:157-161`, `:574-588`, `:591-671`. The user-supplied prototype agrees: `prototype/upload.html:63-67`.
- Lifecycle is implemented through the document library: `web/src/app/(app)/documents/documents-library.tsx:437-484`, `:926-960`; the API uses an action-based dispatcher rather than separate REST verbs: `src/finsight/entrypoints/api/documents.py:283-297`, `:770-777`.

**Do not phrase this as "document management is create/read only".** Delete, restore and purge exist and work; they are just not upload actions.

**Stale source to ignore:** `UI_STANDARDS.md:716` still says "Keep API `upload_type: delete`". That contradicts ADR-0004, the Phase 1 plan, the binding config rule and the as-built API. (`UI_STANDARDS.md` is currently modified in the working tree; it is not edited by this addendum.) The Config Switch Guide is internally inconsistent too: its §5.25 bullet still lists `new`, `update` **or** `delete` as upload types (`docs/plans/project_requirement/finsight_config_switches.md:742`), while its §3 and §4 rules do not (`:115`, `:291`). Follow §3/§4 and the code.

---

## 3. Pilot database is Neon, not Aurora

**Deviation:** the pilot runs on **Neon Postgres with pgvector**. Aurora Serverless v2 + pgvector remains the standard path in code and CDK but is **undeployed in the pilot**.

- The Phase 1 plan and Config Switch Guide specify Aurora: `docs/plans/phase1/phase1_mvp_plan.md:35-36`, `:126`, `:169`, `:275`; `docs/plans/project_requirement/finsight_config_switches.md:225-232`. The later AWS infra plan deliberately changed the pilot to Neon: `docs/plans/aws-infra-cicd-plan.md:17`, `:38-39`, `:56`.
- As-built switch `switches.vector_store` defaults to `neon_pgvector` (`config/schema.yaml:21`, `src/finsight/core/config/models/switches_config.py:14-15`); dev, test and prod use Neon (`config/dev.yaml:12`, `config/test.yaml:11`, `config/prod.yaml:12`). Staging is configured for `aurora_pgvector` (`config/staging.yaml:11`) but staging is not a deployed environment (`docs/plans/aws-infra-cicd-plan.md:6`, `:15`).
- Both adapters are implemented and selected by composition: `src/finsight/composition/container.py:1674-1705`; both paths are tested in `tests/unit/switches/test_vector_store_switch.py:17-27`.
- Prod has no VPC, NAT gateway or Lambda `VpcConfig`: `infra/cdk/app/app.py:74-89`, `infra/cdk/stacks/env_config.py:76-81`, asserted in `infra/cdk/tests/test_pilot_network_synth.py:94-126`. Aurora is only created when the standard path is selected: `infra/cdk/stacks/data.py:321-346`.
- **Implementation is provisioned Aurora, not Serverless v2**, on the standard path: `infra/cdk/stacks/data.py:328-342`. Do not describe the Aurora path as Serverless v2.
- Migration and restore are Neon-based: `scripts/run_migration.py:1-16`, `:32-45`, `:126-150`; `docs/runbook.md:46-54`. The Neon connection string is held in SSM at `/finsight/prod/neon/database_url` (`docs/deployment.md:136-147`). Neon free-plan limits therefore apply (`docs/plans/aws-infra-cicd-plan.md:48`).
- Consequence for Phase 2: do not assume an Aurora cluster, VPC or KMS customer key exists in the pilot. Any new KPI store or chart data path must work against Neon on the pilot path.

---

## 4. The three infra switches (as-built names differ from the plan)

The AWS infra plan names these `vector_store`, `secrets.provider` and `observability.backend` (`docs/plans/aws-infra-cicd-plan.md:17-19`, `:54-58`). The implementation puts all three under the flat `switches:` namespace with different names for two of them.

| Concern | Plan name | **As-built key** | Pilot value | Standard path | Evidence |
| --- | --- | --- | --- | --- | --- |
| Vector/database backend | `vector_store` | `switches.vector_store` | `neon_pgvector` | `aurora_pgvector` | `config/schema.yaml:21`; `src/finsight/core/config/models/switches_config.py:14-15`; selection `src/finsight/composition/container.py:1674-1705` |
| Secrets backend | `secrets.provider` | `switches.secrets_provider` | `parameter_store` | `secrets_manager` | `config/schema.yaml:22`; `src/finsight/core/config/models/switches_config.py:16-17`; selection `src/finsight/composition/container.py:1752-1784`; adapters `src/finsight/adapters/secrets/` |
| Observability/log backend | `observability.backend` | `switches.observability_backend` | `cloudwatch` | `otlp_endpoint` | `src/finsight/core/config/models/switches_config.py:18-19`; consumed in `src/finsight/adapters/tracing/_tracing_config.py:58-71`, `:127-154` |

Additional as-built details:

- `switches.observability_backend` is **not written in any config YAML**; the typed default `cloudwatch` applies. Backend-specific endpoints live under `observability.*` (`src/finsight/core/config/models/observability_config.py:15-23`, `:31-45`). The comment in the model still calls `cloudwatch` the pilot and `otlp_endpoint` the standard path (`src/finsight/core/config/models/switches_config.py:18-19`).
- `switches.secrets_provider` is set only in `config/schema.yaml:22`; no environment YAML overrides it. SSM Parameter Store is the source of truth for secret **values**: `scripts/sync_lambda_env.py:2-24`, `:52-67`; `docs/deployment.md:134-151`. `config/schema.yaml:2` calls itself the source of truth for configuration — read that as non-secret configuration values only.
- Both paths of all three switches are tested and unknown values fail loudly: `tests/unit/switches/test_vector_store_switch.py:17-27`, `tests/unit/switches/test_secrets_provider_switch.py:17-30`, `tests/unit/switches/test_observability_backend_switch.py:27-110`; coverage map `tests/unit/switches/test_switch_coverage.py:20-39`. <!-- pragma: allowlist secret -->
- Only four active switch values are logged at startup (secrets provider, vector store, observability backend, LLM transport) — `src/finsight/core/config/loader.py:191-205` — not all switch values as the Config Switch Guide requires (`docs/plans/project_requirement/finsight_config_switches.md:47`).
- **Extra switch not in either plan's three-switch table:** `switches.llm_transport` with `remote_gateway` / `in_process` (`src/finsight/core/config/models/switches_config.py:20-21`). Prod uses `remote_gateway` (`config/prod.yaml:16-18`, `infra/cdk/config/envs.yaml:64`); dev/staging and the schema default use `in_process` (`config/schema.yaml:26-27`, `infra/cdk/config/envs.yaml:10`, `:39`). Prod therefore builds separate `api.zip` and `gateway.zip` artifacts (`scripts/build_lambda.py:1-20`).

---

## 5. Config values that differ from the Config Switch Guide pilot/standard table

The guide's §3 pilot block (`docs/plans/project_requirement/finsight_config_switches.md:70-238`) uses placeholder providers and several thresholds that were never adopted. Effective config is `config/schema.yaml` deep-merged with `config/<env>.yaml` and validated into typed models (`src/finsight/core/config/loader.py:29-36`, `:128-143`, `:174-189`; `src/finsight/core/config/models/config.py:44-76`).

| Setting | Guide pilot | **As built** | Evidence / note |
| --- | --- | --- | --- |
| `models.answer.primary` | `provider_a/model_strong` (`:138`) | `groq/openai/gpt-oss-120b` | `config/schema.yaml:36` |
| `models.answer.primary_fallbacks` | `provider_b/model_strong`, `provider_c/model_strong` (`:140-141`) | `gemini/gemini-3.6-flash`, `nvidia_nim/google/gemma-4-31b-it` | `config/schema.yaml:38-39`; fallback 3 `self_hosted/open_model_small` still matches (`:40`) |
| `models.answer.cheap` | `provider_a/model_small` (`:143`) | `groq/openai/gpt-oss-20b` | `config/schema.yaml:41`; cheap fallback 2 reuses the primary model (`:44` vs `:36`) |
| `models.embedding.primary` | `provider_a/embed_model` (`:155`) | `gemini/gemini-embedding-001` | `config/schema.yaml:53` |
| `models.rerank.primary` | `self_hosted/cross_encoder_small` (`:161`) | `cohere/rerank-english-v3.0` | `config/schema.yaml:59`. **This also conflicts with D9** ("NVIDIA NIM is the fallback and the reranker", `docs/plans/phase1/phase1_mvp_plan.md:43`, `:206`) — the as-built reranker provider is Cohere. |
| `retrieval.rerank_top_n` | `50` (`:179`) | `20` | `config/schema.yaml:311`, also runtime `reranker.top_n: 20` at `:182` |
| Cache TTL | `cache.ttl_seconds: 3600` (`:192`) | `caches.answer_cache.ttl_seconds: 86400` | `config/schema.yaml:193`; the guide-named key exists only as an unused typed default in `src/finsight/core/config/models/cache_config.py:9` |
| Role cache TTL | `auth.role_cache_seconds: 60` (`:196`) | `caches.role_cache.ttl_seconds: 3600`; key `auth.role_cache_seconds` does not exist | `config/schema.yaml:198`; `src/finsight/core/config/models/role_cache_config.py:11` |
| `auth.refresh_token_days` | `7` (`:197`) | key absent from all config and typed models | `docs/plans/project_requirement/finsight_config_switches.md:197`; `src/finsight/core/config/models/config.py:44-76` |
| Job retry count | `consistency.job_max_receive_count: 5` (`:214`) | effective `3` via `queue.max_receive_count` | `config/schema.yaml:215`; `src/finsight/core/config/models/queue_config.py:17`, `:32-36`. The guide-named field is an unused default (`src/finsight/core/config/models/consistency_config.py:11`). |
| Chunking | "Semantic chunking is not used" (`:711`) | `readers.chunking.strategy: semantic` **and** `ingestion.chunk_strategy: structure_recursive` | `config/schema.yaml:171`, `:286`; both exist as built |
| `environment` | `environment: prod` (`:73`) | `app.environment`: `development`/`test`/`staging`/`production` | `config/schema.yaml:11`, `config/prod.yaml:5`, `src/finsight/core/config/models/environment.py:4-8` |
| `scale.*`, `database.*`, `traffic.*`, `protection.*`, `lambda.*`, `cache.*`, `edge.*` | pilot values in §3 | **No YAML section**; values come from Pydantic defaults only, so a literal `lambda:` block would even be rejected (the typed field is `lambda_`) | `src/finsight/core/config/models/config.py:68-76`, `src/finsight/core/config/models/strict_base_model.py:9-16` |

Also as built and absent from the guide: `models.approved_models` and `models.region` (`config/schema.yaml:34`, `:69-99`), the whole `llm:`, `vector_store:`, `readers:`, `reranker:`, `caches:`, `queue:`, `storage:`, `security:` and `observability:` connection/runtime sections (`config/schema.yaml:105-265`), and `config/test.yaml` (not in the guide's file layout at `:56-64`). The model IDs and rate limits in config follow D9's provider choices rather than the guide's placeholders (`docs/plans/phase1/phase1_mvp_plan.md:43`).

**Standard rollback profile does not exist as a config file.** No `config/*standard*` file sets the guide's standard values (`waf_enabled: true`, `key_mode: kms_customer`, `scan_reader: textract`, `table_reader: textract`, `snapstart_enabled: true`, `rds_proxy_enabled: true`, `standby_reader_enabled: true`, `question_provisioned_concurrency: 2`; guide line 236). Current pilot values remain: `key_mode: aws_managed` in all env files (`config/dev.yaml:122`, `config/test.yaml:273`, `config/staging.yaml:83`, `config/prod.yaml:117`), free readers `tesseract`/`pdfplumber` (`config/schema.yaml:295-296`), WAF off (`infra/cdk/config/envs.yaml:31`, `:56`, `:84`). Note that `docs/plans/phase1/phase1_reconciliation.md:202-217` presents these as pilot values matching the Guide, with standard values only as documented rollback targets — it does not point to a standard config profile, and none exists. Its `min_capacity_acu: 0.5 (staging/prod)` row is also unsupported by any YAML `database:` section.

**Validation rules are only partially enforced.** `docs/plans/phase1/phase1_reconciliation.md:139` claims all 64 §4 rules are enforced; they are not. Enforced rules include model chain shape (`docs/plans/project_requirement/finsight_config_switches.md:254-256`), approved model list (`:253`), reader registration (`:252`), first-token/backup timing (`:265-266`), upload types (`:291`), delta-tracking/chunking rules (`:292`, `:295`) and price-table checks (`:303`). Not enforced, absent or different include: SnapStart/keep-warm requirements (`:249-250`), WAF resource existence as a config check (`:251`), golden-set gates for fallbacks, embedding changes, rerank-size changes and evidence-score changes (`:257-258`, `:270`, `:281`, `:296`, `:301`), `scan_reader: none` producing a clear rejection (`:248` — runtime falls back to the primary reader instead), `auth.role_cache_seconds` / `refresh_token_days` ranges (`:275-276`), the `max_parent_tokens` upper bound (`:297`), and the privileged-role cache rule (`:282` — measured against 3600, not 60). Guardrails that do exist live outside config: cache-key tests (`tests/security/test_cache_keys.py:46-112`), input-gate-before-model ordering in the application flow, and onboarding partition checks in the upload path.

---

## 6. Scope implemented differently, deferred or added

### 6.1 API

- **Action-based document lifecycle.** `POST /documents` dispatches `list`, `recycle`, `delete`, `restore`, `purge`, etc. instead of separate REST endpoints (`src/finsight/entrypoints/api/documents.py:283-297`, `:770-777`). Plans describe "document library and lifecycle endpoints" generically (`docs/plans/phase1/phase1_mvp_plan.md:145`).
- **Question surface has aliases.** `/ask`, `/qa`, `/question`, `/questions` (`src/finsight/entrypoints/api/ask.py:59-63`, `:444-459`; `src/finsight/entrypoints/api/app.py:116-118`). The plan names only a question endpoint (`docs/plans/phase1/phase1_mvp_plan.md:147`).
- **Not mounted / deferred despite handler code or plan claims:**
  - No `/status` router is mounted, so ingestion/job status has no HTTP surface (`src/finsight/entrypoints/api/app.py:101-118`; planned at `docs/plans/phase1/phase1_mvp_plan.md:146`; claimed implemented at `docs/plans/phase1/phase1_reconciliation.md:71`).
  - Onboarding router is included but has no registered routes and no generated client path (`src/finsight/entrypoints/api/onboarding.py:30`, `:369-374`; `src/finsight/entrypoints/api/app.py:103-114`).
  - Source-viewer GET handlers exist but no route decorators are mounted, while the UI calls them (`src/finsight/entrypoints/api/source_viewer.py:7-10`, `:42`, `:589-654`; `web/src/lib/api/events.ts:365-379`, `:400-414`). This is critical: the plan makes source retrieval a Phase 1 security gate (`docs/plans/phase1/phase1_mvp_plan.md:148`, `:159`, `:185`, `:228`). Treat the secured source-viewer HTTP surface as **outstanding as built**, and do not assume it is live in Phase 2.
- **Added endpoints:** `/health`, `/ready`, current-user/users, threads, feedback/report-wrong-source (`src/finsight/entrypoints/api/app.py:87-126`; `web/src/generated/api.d.ts:7`, `:24`, `:245-330`, `:500-602`, `:1503-1554`). These are beyond the plan's contract list.
- **OpenAPI artifacts disagree.** The committed schema `docs/openapi.json` has 96 paths (verified 2026-11-21), matching the generated client `web/src/generated/api.d.ts` and enforced by `scripts/check_openapi.py:12-23`. The root `openapi.json` also has 96 paths but a different set: it still contains unmounted onboarding/source-viewer paths (`openapi.json:500`, `:525`, `:652`, `:719`). Trust `docs/openapi.json` plus the runtime app, not the root file.

### 6.2 UI

- The UI is **implemented**, contrary to `docs/plans/phase1/phase1_reconciliation.md:75`, `:317`, `:334`. Actual pages: `web/src/app/(app)/ask/page.tsx`, `web/src/app/(app)/documents/page.tsx`, `web/src/app/(app)/upload/page.tsx`, `web/src/app/(app)/page.tsx`, `web/src/app/(app)/permission-denied/page.tsx`, `web/src/app/(app)/settings/page.tsx`, `web/src/app/sign-in/page.tsx`.
- Auth as built uses a BFF session cookie and Cognito `USER_SRP_AUTH` kept out of the browser (`web/src/app/api/auth/sign-in/route.ts:24-53`, `web/src/lib/auth/cognito-identity-provider.ts:47-53`, `web/src/app/api/backend/[...path]/route.ts:22-49`) rather than direct browser Cognito integration (`docs/plans/phase1/phase1_mvp_plan.md:161`).
- Sign-in route is `/sign-in`, not the UI standard's `/login` (`UI_STANDARDS.md:244` vs `web/src/app/sign-in/page.tsx:20-30`). Settings is a single permission-gated placeholder (`web/src/app/(app)/settings/page.tsx:11-19`). Dashboard, Charts and Reports are correctly absent (Phase 2/3, `UI_STANDARDS.md:254-256`, `:714`).
- `system_admin` has no `read` action in `config/permissions.yaml:78-80`, so it cannot open `/documents` (`web/src/app/(app)/documents/page.tsx:10-14`), despite the UI standard listing that page for all four roles with the qualifier "System Admin sees file details only" (`UI_STANDARDS.md:247`). Follow the as-built permissions matrix.
- Smaller UI-standard divergences: separate Ask + Stop buttons (`web/src/app/(app)/ask/ask-screen.tsx:692-697`) instead of one transforming button (`UI_STANDARDS.md:285`); generic filter chips instead of scope chips (`web/src/app/(app)/ask/ask-screen.tsx:698-700` vs `UI_STANDARDS.md:284`); plain `N sources` text (`web/src/app/(app)/ask/ask-screen.tsx:628-636` vs `UI_STANDARDS.md:296`); inline thumbs-down reasons (`web/src/app/(app)/ask/ask-screen.tsx:663-669` vs `UI_STANDARDS.md:297`); figures table lacks caption/units/period (`web/src/app/(app)/ask/ask-screen.tsx:638-654` vs `UI_STANDARDS.md:308-312`); source viewer uses `1 / N` + Prev/Next rather than a citation tablist (`web/src/components/ui/source-viewer.tsx:583-612` vs `UI_STANDARDS.md:337`). No explicit row-level View/Update button in the document library (`web/src/app/(app)/documents/documents-library.tsx:782-796`).
- The user-supplied prototype lives at `prototype/`, not `docs/plans/ui/prototype/` as `UI_STANDARDS.md:11-13` says. Parent issue #345 declares `prototype/` the binding UI source; no agent-authored redesign.

### 6.3 Infrastructure and operations

- **Production is deployed; staging/dev are not.** The AWS infra plan scopes deployment to the `prod` environment only (`docs/plans/aws-infra-cicd-plan.md:6`, `:15`). `docs/deployment.md:3-9` records production deployed and `docs/runbook.md:3-7` records rollback verified. Dev/staging parameters were not created (`docs/deployment.md:146-147`).
- **Vercel frontend is not deployed.** The web workflow ends at `npm run build` (`.github/workflows/web.yml:1-49`); frontend deployment is Phase 2 (`docs/plans/aws-infra-cicd-plan.md:21`, `:92`) and is a live Phase 2 decision set (issues #358/#360, `docs/research/vercel-hobby-deployment.md`). The plan's verification checklist line 105 that folds `finsight.sahcreatives.com` into the AWS deploy conflicts with its own out-of-scope lines 6/21/92 — follow those.
- **Observability is CloudWatch-only on the pilot path.** Five degradation alarms, one dashboard and one-month log retention are deployed (`infra/cdk/stacks/observability.py:127-133`, `:145-275`, `:288-323`; `docs/deployment.md:484-487`). ADR-0006 records OTLP-to-CloudWatch plus structured JSON logs as the live alarm source (`docs/adr/0006-otlp-cloudwatch-logs.md:24-53`). The specifically planned **Neon storage metric check** (`docs/plans/aws-infra-cicd-plan.md:84`) is not implemented in the observability stack.
- **Operational dashboards/alarms exist despite Phase 1 D6** saying "no metrics store, dashboards ... alerts" (`docs/plans/phase1/phase1_mvp_plan.md:40`, `:183`). Read D6 as excluding *business* metrics/dashboards/forecasts, not operational CloudWatch alarms.
- **WAF is REGIONAL on API Gateway, not CloudFront**, and is off in every env (`infra/cdk/stacks/api_gateway.py:243-326`, `:249`; `docs/plans/project_requirement/finsight_config_switches.md:94-97`, `:330-331`). There is no CloudFront stack (`infra/cdk/app/app.py:92-134`). The comment in `infra/cdk/stacks/api_gateway.py:5` attributing WAF-off to ADR-0005 is wrong — ADR-0005 is about LLM content capture (`docs/adr/0005-llm-content-capture.md:1`).
- **KMS customer keys are not part of the pilot.** `key_mode: aws_managed` maps to S3-managed and AWS-managed encryption, with no KMS key (`infra/cdk/stacks/data.py:120-129`; `infra/cdk/config/envs.yaml:8`, `:37`, `:62`). The `kms_customer` path exists in code/tests only (`infra/cdk/stacks/data.py:130-142`). This refines the Phase 1 plan's literal "S3 ... KMS encryption" wording (`docs/plans/phase1/phase1_mvp_plan.md:131`).
- Deploy-workflow inconsistencies to be aware of: `FinSight-${CDK_ENV}-Network` is named unconditionally (`.github/workflows/deploy.yml:202`) although prod synthesizes no Network stack; `.github/workflows/release.yml:199-265` provides a second production deploy path without migrate/secret-sync/smoke steps; the production approval gate is "defined but disabled" (`docs/plans/aws-infra-cicd-plan.md:16`) while `docs/deployment.md:19-21`, `:119-123` disagree; and removal of old Network/NAT resources is a documented manual step (`docs/deployment.md:305-334`).

### 6.4 Deviations from the project statement and the HLD

The project statement (`docs/plans/project_requirement/finsightAI.md`) and the Phase 1 HLD (`docs/plans/architecture/phase1/finsight_mvp_hld.svg`) are the top-level parents. Both already narrow Phase 1 to ingestion plus cited Q&A (`docs/plans/project_requirement/finsightAI.md:80-88`; `docs/plans/architecture/phase1/finsight_mvp_hld.svg:4-5`). As built, that narrow reading wins; the broader parent text below is **not** implemented in Phase 1 and belongs to later phases owned by #345.

- **Deferred project-statement scope:** KPI tracking, dashboards/charts, forecasts/scenarios, anomaly/risk alerts, decision recommendations and scheduled reports are stated as objectives and requirements (`docs/plans/project_requirement/finsightAI.md:11-16`, `:20-27`, `:37-43`), but its milestone table places them in Phases 2–3 (`:84-86`). As built there is no business dashboard/chart/report screen (§6.2) and no business alerting — only operational CloudWatch alarms (§6.3).
- **No multi-agent system:** the project statement requires a LangGraph/LangChain supervisor routing to specialist agents (`docs/plans/project_requirement/finsightAI.md:47`), with agentic RAG in Phase 3 (`:86`). There is no LangGraph/LangChain usage under `src/finsight/`; the as-built question flow is the single pipeline drawn in the HLD (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:124-166`).
- **Golden-set release gate not machine-enforced:** the project statement requires a 100+ question golden set, ≥95% numeric accuracy and automatic per-release gating (`docs/plans/project_requirement/finsightAI.md:65-68`); the HLD says a score drop blocks release (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:211-217`). As built, golden-set change gates are absent from config (§5).
- **Residency is in-region US, not in-country:** the project statement requires in-country first with in-region fallback (`docs/plans/project_requirement/finsightAI.md:56`), repeated in the HLD (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:19`, `:224`). The pilot is deployed in `us-east-1` (`docs/deployment.md:29`) and `models.approved_models` lists only US regions (`config/schema.yaml:69-99`). Do not assume in-country data residency in Phase 2 designs; escalate it.
- **HLD infrastructure specifics not built as drawn:** CloudFront + WAF edge (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:22`) — no CloudFront stack and WAF is off and attached to API Gateway (§6.3); SnapStart "on" with weekly republish and keep-warm pings (`:39`, `:58-63`) — `snapstart_enabled` defaults false (`src/finsight/core/config/models/lambda_config.py:7`) and those controls are not implemented (§5); Aurora Serverless per cell (`:175`) — Neon pilot and a provisioned-only Aurora path (§3); S3 encrypted with KMS (`:181`) — S3-managed encryption in the pilot (§6.3); X-Ray tracing every step (`:203`) — no X-Ray instrumentation in application code, tracing is OTLP spans to CloudWatch Logs (`docs/adr/0006-otlp-cloudwatch-logs.md:24-53`); "test, staging, then production" (`:221`) — production-only automatic deployment (§6.3).
- **HLD functions deferred or unmounted:** the Status function (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:46-48`) has no `/status` route, and the Source viewer function (`:54-56`) has handler code but no mounted routes (§6.1).
- **HLD upload form already matches:** "Category, upload type (New, Update)" (`docs/plans/architecture/phase1/finsight_mvp_hld.svg:79`) agrees with §2 — recorded here as alignment, not a deviation.

---

## 7. Stale documents (do not treat as as-built truth)

These records contradict the code or newer decisions. They are listed so agents notice the conflict; parent plans are **not** edited here.

| Record | Stale claim | As-built evidence |
| --- | --- | --- |
| `docs/plans/phase1/phase1_reconciliation.md:75`, `:317`, `:334` | UI not implemented | pages under `web/src/app/` |
| `docs/plans/phase1/phase1_reconciliation.md:68`, `:71`, `:73` | Onboarding, status, source viewer implemented | routers not mounted (§6.1) |
| `docs/plans/phase1/phase1_reconciliation.md:84`, `:202-217`, `:139` | Infra partially deployed; all pilot values/64 rules enforced | `docs/deployment.md:3-9`; §5 |
| `infra/cdk/README.md:3-5`, `:45-48`; `infra/README.md:17-28`; `docs/adr/0002-infrastructure-as-code.md:4`, `:19` | Scaffold only; deploy workflow not implemented | `.github/workflows/deploy.yml`; `docs/deployment.md:3-9` |
| `docs/adr/0006-otlp-cloudwatch-logs.md:60-63` | OTel SDK not vendored | `scripts/build_lambda.py:60-72`; traces at `docs/deployment.md:484-487` |
| `UI_STANDARDS.md:716` | API `upload_type: delete` | ADR-0004; §2 |
| `UI_STANDARDS.md:11-13` | Prototype under `docs/plans/ui/prototype/` | `prototype/` (user-supplied, binding) |
| root `openapi.json:500`, `:525`, `:652`, `:719` | Onboarding/source paths mounted | `docs/openapi.json`; runtime app |

---

## 8. How to use this addendum

1. Read the parent plans for scope and architecture, then this addendum for the current baseline, before touching Phase 1 behaviour.
2. Plan changes against the as-built values and paths recorded here (Neon on the pilot path, `switches.*` keys, `new`/`update` upload only, document-library lifecycle, action-based `POST /documents`, mounted API surface from `docs/openapi.json`), unless doing so would breach a binding policy or a parent plan — in which case stop and escalate.
3. Do not "restore" a parent-plan behaviour listed here as a deviation without an explicit decision and a new ticket. Do not edit the parent plans to make them match the code.
4. When the code changes, update this addendum in the same PR so it stays the as-built truth.
5. `AGENTS.md` links to this file from its Implementation pre-flight section. The Phase 2 spec (`docs/plans/phase2/phase2_spec.md`, produced by issue #360) is required to link here in its "Deviations addendum reference" section; that file does not exist yet and is owned by #360.

---

## 9. Verification notes

- This addendum is documentation only: no adapter code, schema or config value was changed, and no parent plan document was edited.
- Line numbers in `UI_STANDARDS.md` and the root `openapi.json` are quoted as observed on 2026-11-21. `UI_STANDARDS.md` is user-modified in the working tree, so locate the quoted phrase if an anchor has drifted.
