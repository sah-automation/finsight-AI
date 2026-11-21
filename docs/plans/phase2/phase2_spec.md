# Phase 2 Implementation Specification — Metrics, Dashboards, Charts, Full UI and Vercel Cutover

**Status:** Implementation-ready. Planning only; this document changes no code, config, infrastructure or prototype behaviour.
**Owner ticket:** #360 (child of wayfinder map #345). Resolves the handoffs of #351–#359.
**Baseline:** the green `make preflight` of 2026-11-21 (188 architecture tests passed/1 skipped, 982 unit tests, lint, strict types, import contracts, bootstrap parity).

## 0. How to use this spec

1. Read the authoritative parents first: [project statement](../project_requirement/finsightAI.md), [Config Switch Guide](../project_requirement/finsight_config_switches.md), [known risks](../project_requirement/finsight_known_risks.md), [Phase 1 MVP plan](../phase1/phase1_mvp_plan.md) and [ADRs](../../adr/0008-kpi-domain-model.md). Then read the [Phase 1 as-built deviations addendum](../phase1/phase1_as_built_deviations.md) — it is the source of truth for the current baseline.
2. Precedence: binding policies in `AGENTS.md` → parent plans and Config Switch Guide → accepted ADRs → as-built deviations → this spec. If two sources disagree, **stop and escalate**; do not silently pick one. This spec already reconciles the known ADR/as-built tensions in §3.5 and §7.4.
3. All decisions are settled. There is no open design question, no approval gate inside this document and no placeholder value. External owner gates (DNS CNAME, provider keys) are named in §9 and are deployment inputs, not design decisions.
4. `prototype/` is the binding visual source. Do not edit it. Standard-wins differences are listed in §5.4.
5. Follow [CODING_STANDARDS.md](../../../CODING_STANDARDS.md): ports before adapters, `Decimal` never `float`, all figures computed by code, `company_id` on every query, config-only choices, both paths tested, one shared never-log list, spans and metering through decorators.
6. Implementation pre-flight per `AGENTS.md`: `make preflight` on a clean tree; a committed failing port/adapter test in `tests/contract/` or `tests/unit/adapters/` before adapter code; `pytest tests/architecture -q` after scaffolding a new entity/adapter; `make preflight` after each coherent green unit; no `os.getenv`/`os.environ` outside `core/config`.

Decision provenance is tabulated in Appendix A; implementation sequencing is in Appendix B.

---

## 1. Scope restatement

### 1.1 In scope

- **Structured KPI store.** The ten closed KPI codes from ADR-0008 (`revenue`, `gross_margin`, `net_margin`, `operating_expenses`, `cash_flow`, `burn_rate`, `runway`, `dso`, `dpo`, `budget_vs_actual`), computed by pure code from `Metric` rows with provenance, machine status, display labels, conflicts and estimated monthly buckets.
- **Dashboards and charts.** `kpi_current` read view, config-defined chart specifications, the three closed chart types, per-point citations, server-computed changes/shares/variance, optimistic saved layouts, content fingerprints and the `Updating` signal, empty/processing states.
- **Full Phase 1 + 2 UI.** Nine functional screens plus cross-cutting shell and access denied, five Settings panes, token/structure parity with `prototype/`, component and screen accessibility gates aimed at WCAG 2.2 AA.
- **Vercel cutover.** Hobby deployment at the apex domain, sync-then-hook production deploys, closed eight-key SSM→Vercel sync, shared never-log list, web OTLP log forwarding, mock-only previews, rollback.
- **Enablers.** Config sections and validation, permissions additions, golden-set expansion and blocking CI/release gates, observability spans, alarm and runbook.

### 1.2 Explicitly out of scope

- Forecasting, scenarios, anomaly alerts, recommendations, scheduled reports, multi-agent/agentic RAG and query-routing loops — later phases (Phase 3+, per the [project statement milestone table](../project_requirement/finsightAI.md)). `prototype/reports.html` is design reference only; its final placement is **Phase 3**, alongside scheduled reports.
- ERP integrations and mobile app (parent-plan exclusions).
- Staging AWS deployment: `staging` remains a configured-but-undeployed environment and is removed from `web.vercel.preview_api_target`.
- Log-redaction audit (R16) and the customer-managed-encryption-key switch (R2).
- New KPI codes, `breakdown_pie`, a full-screen chart route, a KPI document category, dashboard/chart response caches, DynamoDB layouts, a server-side PNG/PDF renderer, `golden_set.tolerances_file`, a free export filename/metadata template, `dashboard.layout_store`, a visible dashboard refresh control, prototype edits, and any new switch that can disable an evidence, output, citation, role, metering, redaction or config check.
- Root `openapi.json` is not the contract artifact: regenerate `docs/openapi.json` and `web/src/generated/api.d.ts` and keep `scripts/check_openapi.py` green.

---

## 2. Domain model

Terms are defined in [GLOSSARY.md](../../../GLOSSARY.md); use those names verbatim in code, tests, issues and copy.

| Term / link | Implementation meaning |
| --- | --- |
| [Metric](../../../GLOSSARY.md) | Raw extracted figure with provenance (company, document, page, chunk, version, currency, units). Margin inputs (COGS, net income) are Metrics so code computes margin percentages. |
| [KPI](../../../GLOSSARY.md) | Code-computed, period-bucketed series derived from Metrics. Closed ten-code list; the model never authors or edits a value. |
| [ComputationStatus](../../../GLOSSARY.md) | `computed`, `estimated` or `needs_review` on each KPI row. Composite KPIs (`runway`, `dso`, `dpo`, `budget_vs_actual`) are `needs_review` when any required input is missing; no guessing, borrowing or conversion. |
| [EstimatedLabel](../../../GLOSSARY.md) / [DeclaredPeriod](../../../GLOSSARY.md) | A quarterly source figure spread over months keeps `period` = source-declared text (e.g. `2026-Q3`), gains `chart_period` (e.g. `2026-07`), `computation_status: estimated`, `estimation_method: quarterly_spread_equal` and the `Estimated` display label. It is never presented as a source-stated figure. |
| [NeedsReview](../../../GLOSSARY.md) | Missing input or exact-match failure for `budget_vs_actual`. `budget_vs_actual` compares only when source `period`, `currency` and `units` all match exactly (`kpi.budget_vs_actual_match: strict`). |
| [Supersession](../../../GLOSSARY.md) / [KPI Conflict](../../../GLOSSARY.md) | Same-document history uses stored `superseded_by_document_version_id`; no conflict id is stored. Cross-document conflicts are derived on read (`kpi_current`); final beats draft and newer beats older for the chosen value, but both cited rows persist as `computed` and are shown with distinguishing labels (R28). |
| [Display Label](../../../GLOSSARY.md) | `Draft` from the source document version status, `Estimated` from `computation_status`, `Updating` injected by the API from staleness. Precedence: `Updating` > `Estimated` > `Draft`; plain final figures use `null`. |
| [Chart Specification](../../../GLOSSARY.md) / [Chart Series](../../../GLOSSARY.md) | A config `chart_id` fixes type, KPIs, periods, breakdown, diverging flag and polarity. The API returns ready-to-draw decimal-string series with per-point provenance, status and label; the client never computes figures. |
| [Dashboard Layout](../../../GLOSSARY.md) | A user's ordered KPI codes and chart ids with `full`/`half` spans, keyed `(company_id, user_id)`, carrying only identifiers, `contract_version`, integer `version` and `updated_at` — no figures, timestamps, fingerprints or builder snapshots. |
| [Freshness Fingerprint](../../../GLOSSARY.md) | A canonical hash of the winning rows' `kpi_code`, `period`, `chart_period`, `document_version_id`, `computation_rule_version`, exact value, status, citations and conflict/supersession markers. Exclude `created_at`/`updated_at`. Derived on read, never stored or cached. |
| [Update Cascade](../../../GLOSSARY.md) | Document update → Metric re-extraction → KPI recompute in the ingestion transaction → after-commit `kpi.recomputed` hint → changed fingerprint on poll → `Updating` badge → full data on user interaction. |
| [Export Payload](../../../GLOSSARY.md) / [Role](../../../GLOSSARY.md) | One chart response feeds rendering and browser-side PNG/PDF; it carries only what the current role may see and has an opaque identifier in the filename. |

**KPI row fields (all exposed by `GET /kpis`):** `company_id` (internal, never in the client payload), `kpi_code`, `period`, `period_start`, `chart_period`, `chart_period_start`, `currency`, `units`, `value` (exact decimal string), `source_citations`, `computation_status`, `estimation_method`, `document_version_id`, `computation_rule_version`, `superseded_by_document_version_id`, conflict marker, `created_at`, `updated_at`.

---

## 3. Architecture additions

### 3.1 KPI materialisation in the ingestion pipeline

- Add a pure-code KPI computation step to the existing ingestion pipeline (after Metric extraction/table persistence, before the document stamp and change events). It reads Metrics through a repository port, computes all ten codes where inputs exist, and returns rows; it performs no I/O of its own and never calls a model.
- KPI rows are upserted **in the same transaction** as chunks, vectors, Metrics, document stamp and change events. A failed commit leaves neither KPI rows nor an event. Use upsert on the storage key; never `DELETE` before recompute.
- With `switches.delta_tracking: true`, compare extracted figures with the previous document version and recompute every KPI that depends on a changed, added or removed figure, including indirect dependencies whose own chunk did not change. With `delta_tracking: false`, re-extract everything and recompute every KPI for the new version. Both paths must produce byte-identical final KPI rows; a test runs one update through both and compares.
- The `kpi.recomputed` invalidation event is published **after commit** through an outbox/after-commit mechanism (the as-built change-event publisher is best-effort in memory). Payload: `company_id`, affected `kpi_code`s and periods, `document_version_id`, `computation_rule_version`, lineage/conflict markers. It is a hint only: no consumer, especially the dashboard, writes layout rows or badge state from it.
- New ports live in `domain/ports/`; Postgres/Neon repositories in `adapters/repositories/`; computation in `domain/services/`; orchestration in `application/metrics/`. No adapter reads env/config directly; settings arrive through constructor injection from the config module.

### 3.2 KPI store

One KPI table (`kpi_values`) plus the `kpi_current` read view. No separate monthly table and **no monthly partitioning in Phase 2**: Phase 1 already partitions by company, and a quarterly row has no single month. If load later demands partitioning, partition by company first and use `period_start` inside it.

```sql
CREATE TABLE kpi_values (
  company_id                       UUID        NOT NULL,
  kpi_code                         TEXT        NOT NULL,
  period                           TEXT        NOT NULL,  -- source-declared label
  document_version_id              UUID        NOT NULL,
  chart_period                     TEXT        NOT NULL,  -- = period for non-estimated rows
  period_start                     DATE        NOT NULL,  -- derived from period, checked
  chart_period_start               DATE        NOT NULL,  -- derived, checked
  currency                         TEXT        NOT NULL,
  units                            TEXT        NOT NULL,
  value                            NUMERIC     NULL,      -- NULL only with computation_status needs_review
  computation_status               TEXT        NOT NULL,
  estimation_method                TEXT        NULL,
  source_citations                 JSONB       NOT NULL,
  computation_rule_version         TEXT        NOT NULL,
  superseded_by_document_version_id UUID       NULL,
  created_at                       TIMESTAMPTZ NOT NULL,
  updated_at                       TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (company_id, kpi_code, period, document_version_id, chart_period)
);
CREATE INDEX kpi_values_company_code_start ON kpi_values (company_id, kpi_code, period_start DESC);
CREATE INDEX kpi_values_company_chart_start ON kpi_values (company_id, chart_period_start);
```

- Dates are derived from text labels in code and checked for agreement; never trust a client-supplied date. Missing units mean `needs_review`, never a guessed scaling.
- The table must work on **Neon in the pilot** (the standard path is provisioned Aurora, not Aurora Serverless v2). Sizing estimate: ~2.16M monthly rows ≈ 500 MB, inside the Neon free-plan ceiling; pgvector coexists in the same database.
- `kpi_current` applies final > newer selection, keeps both cited rows when a real conflict persists, honours retention deletion (`version_retention_days`, `deleted_retention_days`) and exposes supersession as history only. Role-based content filtering happens in the handlers (§4.5), not in this view.
- `kpi_rebuild_state` is keyed by target `computation_rule_version` with state `pending`/`running`/`complete`. A new rule version cannot become active until its rebuild is `complete` (same gate pattern as embedding changes).

### 3.3 Chart series API

- `GET /charts/{chart_id}` resolves a config `charts.specs` entry. Optional overrides (`chart_type`, repeatable `kpi_code`, `period_from`, `period_to`, 2–4 `periods`, `breakdown_key`, `breakdown_period`) may only select values allowed by that spec; fixed and overridden requests return the same shape.
- Closed chart-type enum: `trend_line`, `comparison_bar`, `breakdown_bar`. Budget-vs-actual variance uses `comparison_bar` with spec `diverging: true` and a `variance_rows[]` array of server-computed actual/budget/variance decimal strings and favourable/unfavourable flags. No `breakdown_pie`.
- Each point carries its own `value`, `period`, `chart_period`, `source_citations`, `computation_status`, `display_label`, `change`, `change_direction` (from spec `polarity`), `share` and a reason string when `value` is `null`. Changes, shares, directions and axis scales are computed by code and sent by the API; the client does not recompute them. Empty data is a normal 200 with empty arrays and an `insufficient_data` reason.
- No literal limits or allow-lists in code: page size, allowed chart types, KPI codes, breakdown keys, polarity, diverging flag, spans and periods live in the config sections of §6.

### 3.4 Saved layouts

```sql
CREATE TABLE dashboard_layouts (
  company_id       UUID        NOT NULL,
  user_id          UUID        NOT NULL,
  contract_version INTEGER     NOT NULL,
  kpi_codes        JSONB       NOT NULL,  -- ordered, closed-set codes only
  charts           JSONB       NOT NULL,  -- ordered [{chart_id, span: full|half}]
  version          INTEGER     NOT NULL,
  updated_at       TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (company_id, user_id)
);
```

- **Reconciliation of ADR-0011 with the as-built baseline:** this is source-of-truth data in the relational store behind the existing `switches.vector_store` path — **Neon on the pilot**, provisioned Aurora on the standard path. ADR-0011's "Aurora, not DynamoDB" means "relational source of truth, never a DynamoDB view/cache"; it does not license assuming an Aurora cluster in the pilot. No `layout_store` key and no second store path.
- Both ids come from the authenticated context. A missing row returns the config default and **no row is written on open**. No audit entry is required for a layout save.
- A save sends the loaded `version`; the conditional update succeeds only when it matches, then increments it by one; the first save succeeds only when no row exists. A stale version returns 409 with the current layout and the "layout changed elsewhere" message. No confirmation modal.
- Reads and saves drop KPI codes and `chart_id`s the role may not see (§4.5) and skip ids unknown to config; if nothing remains, the config default is used. Dropped ids are not rejected.

### 3.5 Update cascade and staleness

1. Document update → Metric re-extraction → KPI recompute/upsert in the ingestion transaction (§3.1).
2. After commit, `kpi.recomputed` is emitted as a best-effort hint; loss, duplication or reordering can only delay the badge to the next poll.
3. The fingerprint route hashes `kpi_current` per chart spec (§2). Identical recomputes produce identical fingerprints; document version, rule version, value, status, citation or conflict changes produce a new one.
4. The page polls `GET /dashboard/fingerprints` every `dashboard.auto_refresh_seconds` (5–300, default 30), pausing while the tab is hidden. Only fingerprints cross the wire on poll; no chart data, citations or document names.
5. A mismatch injects `Updating` for that chart (precedence §2) and shows the top warning notice when any visible chart is stale. Previously loaded figures stay on screen. Full data is fetched only on user interaction: opening the KPI drawer, expanding/navigating to a chart, changing period/range, or reloading. There is no visible refresh control.
6. Empty state comes from `GET /kpis?limit=1` with no filters: `documents_processing: true` → "Figures are being prepared."; otherwise "No figures yet" with Upload only when `actions.upload` is true, else "Ask your finance team to upload documents." No polling or layout write while empty.
7. Missing-input rows remain `needs_review` with `null`; R28 conflicts keep both cited rows and change the fingerprint through their stable fields.

### 3.6 Rebuild job

- A config change to a KPI definition, computation rule, estimation method or `computation_rule_version` triggers a rolling, idempotent rebuild of KPI rows from existing Metrics, a few companies at a time under the existing fair-share limits.
- `rebuild_priority` accepts only the named ranks `rebuilds` and `background`, mapped **below** live questions and uploads; startup validation rejects live/upload values and asserts that ordering. `rebuild_batch_size` must be positive.
- The job sets `kpi_rebuild_state.complete` only after every company succeeds; retrying a failed company is safe because upserts use the storage key. It never issues `DELETE` before recompute; older document-version rows remain as audit/superseded history until retention removes them.
- The config change ships as its own release with both paths tested (Config Switch Guide rules 6, 7 and 11).

---

## 4. API contracts

All routes take company and user from the authenticated context only. There is no `/companies/{company_id}` path segment; dev `x-company-id`/`x-role` headers never override ASGI-scope Cognito claims. New routes must be added to `docs/openapi.json` and `web/src/generated/api.d.ts` with `scripts/check_openapi.py` green. `contract_version: 1` allows additive future changes.

### 4.1 `GET /kpis`

```yaml
paths:
  /kpis:
    get:
      operationId: list_kpis
      parameters:
        - {name: kpi_code, in: query, required: false, schema: {type: array, items: {type: string, enum: [revenue, gross_margin, net_margin, operating_expenses, cash_flow, burn_rate, runway, dso, dpo, budget_vs_actual]}}}
        - {name: period_from, in: query, schema: {type: string}}
        - {name: period_to, in: query, schema: {type: string}}
        - {name: currency, in: query, schema: {type: string}}
        - {name: units, in: query, schema: {type: string}}
        - {name: limit, in: query, schema: {type: integer, minimum: 1, maximum: 100}}  # from kpi.page_size_max
        - {name: cursor, in: query, schema: {type: string}}
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/KpiListResponse'
components:
  schemas:
    KpiRow:
      type: object
      required: [kpi_code, period, period_start, chart_period, chart_period_start, currency, units, value, source_citations, computation_status, document_version_id, computation_rule_version, created_at, updated_at]
      properties:
        kpi_code: {type: string}
        period: {type: string}
        period_start: {type: string, format: date}
        chart_period: {type: string}
        chart_period_start: {type: string, format: date}
        currency: {type: string}
        units: {type: string}
        value: {type: string, nullable: true}          # exact decimal string, never a JSON number
        source_citations: {type: array, items: {type: string}}
        computation_status: {type: string, enum: [computed, estimated, needs_review]}
        estimation_method: {type: string, nullable: true}
        document_version_id: {type: string, format: uuid}
        computation_rule_version: {type: string}
        superseded_by_document_version_id: {type: string, format: uuid, nullable: true}
        conflict_marker: {type: string, nullable: true}
        created_at: {type: string, format: date-time}
        updated_at: {type: string, format: date-time}
    KpiListResponse:
      type: object
      required: [contract_version, items, next_cursor, documents_processing, actions]
      properties:
        contract_version: {type: integer, enum: [1]}
        items: {type: array, items: {$ref: '#/components/schemas/KpiRow'}}
        next_cursor: {type: string, nullable: true}
        documents_processing: {type: boolean}
        actions: {type: object, required: [upload], properties: {upload: {type: boolean}}}
```

- Ordered by `period_start` descending, cursor-paginated; default page size 50 and maximum 100 come from `kpi.page_size_default`/`kpi.page_size_max` (ADR-0010's page-size handoff, keyed here). `period_from`/`period_to` filter on `period_start`, charts bucket on `chart_period_start`.
- `documents_processing` is true when any document version for the company is `received`/`stored`/`processing` — no titles or ids. `actions.upload` is derived from `kpi_view` context plus the role's `upload` action on at least one document category (today: planners only).
- No sixth `chart_view` action; no export flags in this envelope.

### 4.2 `GET /charts/{chart_id}`

```yaml
paths:
  /charts/{chart_id}:
    get:
      operationId: get_chart
      parameters:
        - {name: chart_id, in: path, required: true, schema: {type: string}}
        - {name: chart_type, in: query, schema: {type: string, enum: [trend_line, comparison_bar, breakdown_bar]}}
        - {name: kpi_code, in: query, schema: {type: array, items: {type: string}}}
        - {name: periods, in: query, description: '2-4, only values allowed by the spec', schema: {type: array, items: {type: integer}}}
        - {name: breakdown_key, in: query, schema: {type: string}}
        - {name: breakdown_period, in: query, schema: {type: string}}
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ChartResponse'
components:
  schemas:
    ChartPoint:
      type: object
      required: [value, period, chart_period, source_citations, computation_status, display_label]
      properties:
        value: {type: string, nullable: true}
        period: {type: string}
        chart_period: {type: string}
        source_citations: {type: array, items: {type: string}}
        computation_status: {type: string, enum: [computed, estimated, needs_review]}
        display_label: {type: string, enum: [Draft, Estimated, Updating], nullable: true}
        change: {type: string, nullable: true}
        change_direction: {type: string, enum: [good, bad], nullable: true}
        share: {type: string, nullable: true}
        reason: {type: string, nullable: true}
    ChartDataset:
      type: object
      required: [series_type, label, currency, units, period, data, points]
      properties:
        series_type: {type: string, enum: [kpi, forecast, anomaly]}  # only kpi in Phase 2
        label: {type: string}
        currency: {type: string}
        units: {type: string}
        period: {type: string}
        data: {type: array, items: {type: string, nullable: true}}
        points: {type: array, items: {$ref: '#/components/schemas/ChartPoint'}}
    VarianceRow:
      type: object
      required: [name, actual, budget, variance, favourable]
      properties:
        name: {type: string}
        actual: {type: string, nullable: true}
        budget: {type: string, nullable: true}
        variance: {type: string, nullable: true}
        favourable: {type: boolean}
    ExportMetadata:
      type: object
      required: [generated_at, company_name, company_slug, period_range, currency, units, source_document_list]
      properties:
        generated_at: {type: string, format: date-time}   # server-generated UTC
        company_name: {type: string}                     # appears only inside export content
        company_slug: {type: string}                     # opaque, not derived from company data
        period_range: {type: string}
        currency: {type: string}
        units: {type: string}
        source_document_list: {type: array, items: {type: object, properties: {title: {type: string}, version: {type: string}}}}
    ChartResponse:
      type: object
      required: [contract_version, chart_id, labels, datasets, export]
      properties:
        contract_version: {type: integer, enum: [1]}
        chart_id: {type: string}
        labels: {type: array, items: {type: string}}
        datasets: {type: array, items: {$ref: '#/components/schemas/ChartDataset'}}
        variance_rows: {type: array, items: {$ref: '#/components/schemas/VarianceRow'}}
        reason: {type: string, nullable: true}
        export: {$ref: '#/components/schemas/ExportMetadata'}
```

- `source_document_list` titles and versions are resolved server-side because the source-viewer HTTP surface is not mounted as built (§5.3 prerequisite).
- Export filenames: `chart-{chart_id}-{opaque_company_id}-{date}.{png,pdf}` for Charts-page exports and `dashboard-{opaque_company_id}-{date}.pdf` for dashboard exports. No company name, slug or readable identifier in a filename or log. PNG and PDF are generated in the browser from this response; there is no export endpoint and no server renderer.

### 4.3 `GET /dashboard/fingerprints`

```yaml
paths:
  /dashboard/fingerprints:
    get:
      operationId: get_dashboard_fingerprints
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                required: [contract_version, charts]
                properties:
                  contract_version: {type: integer, enum: [1]}
                  charts:
                    type: object
                    additionalProperties: {type: string}   # chart_id -> fingerprint
                    description: 'Fingerprints only; no figures, citations or document names.'
```

Charts the role may not see are omitted entirely. Specs resolved exactly as in `/charts/{chart_id}`.

### 4.4 Saved layout routes

```yaml
paths:
  /dashboard/layout:
    get:
      operationId: get_dashboard_layout
      responses:
        '200': {description: 'Saved layout or config default; no row written on a miss'}
    put:
      operationId: save_dashboard_layout
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [contract_version, kpi_codes, charts, version]
              properties:
                contract_version: {type: integer, enum: [1]}
                kpi_codes: {type: array, items: {type: string}}
                charts: {type: array, items: {type: object, required: [chart_id, span], properties: {chart_id: {type: string}, span: {type: string, enum: [full, half]}}}}
                version: {type: integer, minimum: 0}
      responses:
        '200': {description: 'Saved; version incremented'}
        '409': {description: 'Stale version; current layout returned for reapplication', content: {application/json: {schema: {type: object, required: [error, current_layout], properties: {error: {type: string, enum: [layout_changed]}, current_layout: {type: object}}}}}}
```

### 4.5 Role enforcement points

| Surface | Required action | Enforcement |
| --- | --- | --- |
| `/kpis`, `/charts/{chart_id}` | `kpi_view` | Shared permission dependency before data access; handler re-checks and filters rows, points, citations and `source_document_list` by the cited document's category and the role's `access_scope`. |
| `/dashboard/fingerprints`, `GET /dashboard/layout` | `dashboard_view` | Same two-layer pattern; omit fully invisible `chart_id`s from fingerprints and layouts. |
| `PUT /dashboard/layout` | `dashboard_edit_layout` | Same two-layer pattern; drop unpermitted ids before persisting instead of rejecting. |
| Export buttons / navigation | `chart_export`, `kpi_export` | Not endpoints; flow through the existing current-user `permission_actions`/`actions` surface. Export uses only content already returned by the API. |
| Upload state in `/kpis` | derived `upload` action | True only when the role holds `upload` on at least one document category. |

- API Gateway remains **authentication-only** (JWT). There is no RBAC-enforcing authorizer and no new BFF middleware layer.
- Unknown role or unknown action is denied. No wildcard and no default: remove the legacy `permissions.get('default')` fallback and `'*'` allowance in `PermissionPolicy` rather than extending them.
- KPI visibility follows the cited source document; there is no KPI category and no row-level KPI mapping. Hidden series leave no placeholder, count or other hint. A fully hidden chart yields a normal empty dataset and is omitted from layouts/fingerprints.
- No dashboard/chart response cache in Phase 2. Each request reads `kpi_current`; the answer cache key stays unchanged.

---

## 5. UI specification

The binding source is [`prototype/`](../../../prototype/README.md). Acceptance means token and structure parity, correct states and copy, and the accessibility gate in §5.5 — not a pixel diff.

### 5.1 Screen-by-screen acceptance

| Screen | Prototype | Acceptance highlights |
| --- | --- | --- |
| Sign-in | [login.html](../../../prototype/login.html) | Cognito SRP with as-built route `/sign-in`; three drawn states plus approved copy; MFA challenge for System Admin and Executive Leadership is provider-hosted ("specified by standard, not drawn"), no new app screen. |
| Upload | [upload.html](../../../prototype/upload.html) | New/Update segmented control only; duplicate warning, partition-missing replacement, per-file progress and validation; no delete control (ADR-0004). |
| Documents library | [documents.html](../../../prototype/documents.html) | Filters, sort, drawer; Delete stays here; API-driven pager styled with existing tokens; System Admin is denied the page as built. |
| Recycle bin | [documents.html](../../../prototype/documents.html) | Segmented Documents view, not a separate route; restore and Delete permanently with the drawn confirmation and toast, gated by §7.4. |
| Ask | [ask.html](../../../prototype/ask.html) | Status/skeleton within 100 ms; whole verified sentences only; check failure keeps shown sentences; "Waking up, please wait." after 2 s and "Still working on your question." after 8 s (fake clock); Stop keeps shown sentences and reads "Stopped. Ask again or rephrase."; insufficient data and denied states leak nothing; no raw errors. |
| Source viewer | [ask.html](../../../prototype/ask.html) | Ask panel with cited version shown, never swapped; "No longer available" and "no access" share one non-leaking screen; "Open full document" only when the API grants it; 480px column ≥1181px, floating panel 901–1180px, bottom sheet ≤900px; `Esc` closes and returns focus to the chip; focus trapped at each width. |
| Settings | [settings.html](../../../prototype/settings.html) | All five panes (Profile, Notifications, Users, Audit log, Cost view) with prototype role visibility; email-only (Push and "Mentions" removed); unknown section falls back to Profile. |
| Dashboard | [dashboard.html](../../../prototype/dashboard.html) | KPI cards, 480px metric drawer, two trend cards, variance card; badges from `display_label` with `Updating > Estimated > Draft`; top warning on any stale chart; empty states from §3.5; no refresh control; stale save returns current layout with the inline notice, no modal. |
| Chart detail | [charts.html](../../../prototype/charts.html) | `/charts` is the detail view; dashboard expansion navigates with the selected `chart_id`; no full-screen route; builder choices map to config-bounded overrides; `Image`/`PDF` only where drawn; source caption/row is the citation list; table fallback matches the chart. |
| App shell | [shell.js](../../../prototype/shell.js) | Sidebar, phone menu, command menu, shortcuts; authorized capabilities come from the API, never a role name or `sessionStorage`. |
| Access denied | [not-allowed.html](../../../prototype/not-allowed.html) | Direct visits to forbidden URLs show exactly "You don't have access to this." from the messages file. |

`prototype/reports.html` is **not** accepted in Phase 2 (Phase 3 design reference). Inline Ask charts are accepted only when the answer response carries a chart payload; the client never invents one.

### 5.2 Visual and copy parity

- One shared token source; a `web/test/` machine test reads `prototype/styles.css` and fails if app colour/type/spacing values differ. No raw value is hand-copied into a component.
- All copy comes from `web/src/lib/messages.ts`. New approved strings: "Still working on your question.", "Figures are being prepared.", "The layout changed elsewhere. Check the current layout and save again to reapply." ("Stopped. Ask again or rephrase." and the access-denied string already exist verbatim).
- Layout, component order and the four states (loading, empty, error, success) match the prototype. Committed snapshots at 390, 768 and 1280 px under `web/snapshots/` with an `APPROVALS.md` entry naming approver, date and browser for each screen. No pixel-diff threshold.
- Allowed differences: real API data replaces sample numbers/labels/controls; API capabilities replace the `can` table and preview role; email-only notifications; API pager; provider-hosted MFA; standard-wins accessibility fixes; API-driven dashboard labels and export metadata; source-viewer prerequisite. Nothing else is a redesign.

### 5.3 Backend prerequisites for UI acceptance

- Mount the source-viewer GET handlers with company, role and access-scope enforcement before any citation-click test can pass; a UI-only panel does not count.
- Add the five ADR-0012 actions and `document_purge` (§7) to the current-user capability surface, OpenAPI and generated client; per-role tests assert unpermitted controls are **absent from the DOM**, not disabled or CSS-hidden. Disabled state is reserved for non-access reasons (Save before a change, incomplete form, sign-in during an outage).
- Exports use §4.2 metadata; the prototype's title-based filename and `window.print()` PDF are illustrations, not acceptance.

### 5.4 Standard-wins differences from the prototype

Add the skip link, focus trapping and focus ring; respect 44px touch targets; never use `--text-muted` on `--bg-subtle` (use `--text-secondary`); remove prototype-only controls (role/sign-in/state selectors, sample labels, sessionStorage role); use `/sign-in` not `/login`; deny System Admin on Documents; email-only notifications; API-driven pager; no full-screen chart; no visible refresh control. These are deliberate, recorded deviations — do not "restore" the prototype behaviour.

### 5.5 Accessibility and component test requirements

- Component `vitest-axe` and screen `@axe-core/playwright`: **zero serious or critical violations**; add the missing libraries and harness.
- Keyboard-only walkthrough per screen; chart table fallback with real data whose numbers, units and periods match the chart when read out; contrast checks for chart colours and evidence highlight; series never distinguished by colour alone.
- One written manual pass per screen: NVDA + Firefox desktop and VoiceOver + Safari iOS phone sheet; record tester, date, browser and screen reader. A serious finding blocks that screen; repeat after major changes.
- Per-component tests: all four states, copy from messages file, permission absence per role, badge precedence, fake-clock timings, `Esc`/focus return for panels, source version not swapped, opaque export filenames, and API-provided values only.
- Claim wording is **"aims for WCAG 2.2 AA, checked by these tests"**, not formal conformance without an audit.

---

## 6. Config surface

All keys are typed Pydantic sections in `config/schema.yaml`, wired into `Config`, validated at startup by model validators and `Config.validate_binding_rules()`, with `extra='forbid'`. Missing, misspelled, unknown or invalid values stop startup. Every value below is identical in pilot and standard unless stated; none is a runtime quality switch.

```yaml
kpi:
  codes: [revenue, gross_margin, net_margin, operating_expenses, cash_flow, burn_rate, runway, dso, dpo, budget_vs_actual]
  budget_vs_actual_match: strict
  estimation_methods:
    revenue: quarterly_spread_equal
    gross_margin: quarterly_spread_equal
    net_margin: quarterly_spread_equal
    operating_expenses: quarterly_spread_equal
    cash_flow: quarterly_spread_equal
    burn_rate: quarterly_spread_equal
    runway: quarterly_spread_equal
    dso: quarterly_spread_equal
    dpo: quarterly_spread_equal
    budget_vs_actual: quarterly_spread_equal
  tolerances:
    revenue:            {kind: percent_of_expected_plus_absolute_floor, percent: 0.5, floor: 1000, floor_unit: kpi_currency}
    gross_margin:       {kind: absolute, value: 0.25, unit: percentage_points}
    net_margin:         {kind: absolute, value: 0.25, unit: percentage_points}
    operating_expenses: {kind: percent_of_expected_plus_absolute_floor, percent: 0.5, floor: 1000, floor_unit: kpi_currency}
    cash_flow:          {kind: percent_of_expected_plus_absolute_floor, percent: 0.5, floor: 1000, floor_unit: kpi_currency}
    burn_rate:          {kind: percent_of_expected, percent: 5}
    runway:             {kind: percent_of_expected, percent: 5}
    dso:                {kind: absolute, value: 3, unit: days}
    dpo:                {kind: absolute, value: 3, unit: days}
    budget_vs_actual:   {kind: exact_or_needs_review}
  page_size_default: 50
  page_size_max: 100
  rebuild_batch_size: 10
  rebuild_priority: rebuilds        # or background; both rank below live questions and uploads

charts:
  specs:
    revenue_trend:
      chart_id: revenue_trend
      chart_type: trend_line
      kpi_codes: [revenue]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: higher_is_better
    margin_trend:
      chart_id: margin_trend
      chart_type: trend_line
      kpi_codes: [gross_margin, net_margin]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: higher_is_better
    cash_flow_comparison:
      chart_id: cash_flow_comparison
      chart_type: comparison_bar
      kpi_codes: [cash_flow]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: higher_is_better
    expense_comparison:
      chart_id: expense_comparison
      chart_type: comparison_bar
      kpi_codes: [operating_expenses]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: lower_is_better
    burn_comparison:
      chart_id: burn_comparison
      chart_type: comparison_bar
      kpi_codes: [burn_rate]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: lower_is_better
    runway_comparison:
      chart_id: runway_comparison
      chart_type: comparison_bar
      kpi_codes: [runway]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: higher_is_better
    collection_periods:
      chart_id: collection_periods
      chart_type: comparison_bar
      kpi_codes: [dso, dpo]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: false
      polarity: lower_is_better
    budget_variance:
      chart_id: budget_variance
      chart_type: comparison_bar
      kpi_codes: [budget_vs_actual]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: []
      diverging: true
      polarity: neutral
    revenue_breakdown:
      chart_id: revenue_breakdown
      chart_type: breakdown_bar
      kpi_codes: [revenue]
      supported_periods: [4, 6, 8]
      periods_selectable: [2, 3, 4]
      breakdown_keys: [document_category]
      diverging: false
      polarity: higher_is_better
  export_formats: [png, pdf]

dashboard:
  auto_refresh_seconds: 30         # 5..300
  default_layout:
    kpi_codes: [revenue, gross_margin, net_margin, operating_expenses, cash_flow, burn_rate]
    charts:
      - {chart_id: revenue_trend, span: full}
      - {chart_id: margin_trend, span: half}
  staleness_badge_enabled: true    # fixed on; not a switch

web:
  vercel:
    sync_enabled: true              # fixed on; no off path
    preview_api_target: mock        # only allowed value; staging removed
    log_forwarding_enabled: true    # fixed on
    log_retention_days: 30
    never_log_file: config/never_log.yaml
    otlp_log_group: /aws/finsight/web-prod

golden_set:
  kpi_questions_path: tests/golden/questions/phase2_kpi.yaml
```

### 6.1 Validation rules

- `kpi.codes` is exactly the closed ADR-0008 set; every code has one estimation method and one tolerance; tolerance keys equal the code set. Tolerance union is discriminated by `kind` with `extra='forbid'`: `percent_of_expected_plus_absolute_floor` (`percent > 0`, `floor > 0`, `floor_unit == kpi_currency`), `absolute` (`value > 0`, `unit in [percentage_points, days]`), `percent_of_expected` (`percent > 0`), `exact_or_needs_review` (no numeric fields).
- `kpi.budget_vs_actual_match` is `strict` only; `rebuild_batch_size` is positive; `page_size_default`/`page_size_max` are positive integers with `page_size_default <= page_size_max`. `charts.specs` keys match `chart_id`; chart types use the closed enum and the concrete specs above cover every KPI code and all three chart types; allow-lists are config-bounded; `breakdown_keys` may contain only source metadata keys present on Metrics (`document_category`); `diverging: true` only on a `comparison_bar` spec containing `budget_vs_actual`; `export_formats` is a subset of `[png, pdf]`. There is no free filename or metadata template.
- `dashboard.auto_refresh_seconds` in 5–300; default layout codes resolve to `kpi.codes`, chart ids to `charts.specs`, spans to `full|half`, no duplicates; `staleness_badge_enabled` must be `true`. `layout_store` must be absent.
- `web.vercel.sync_enabled`, `log_forwarding_enabled` and `dashboard.staleness_badge_enabled` must be `true`; `preview_api_target` must be `mock`; retention is a positive int; the never-log path is repo-relative and readable (default `config/never_log.yaml`); log group is a non-empty string. The eight-key SSM allow-list belongs to `scripts/sync_vercel_env.py` and its tests, not app YAML.
- `golden_set.kpi_questions_path` must be a non-empty path under `tests/golden/questions/`; `tolerances_file` must be absent (schema forbids it).
- No switch may disable evidence checks, output gate, citation requirements, role enforcement, metering, log redaction or config validation (Config Switch Guide §1 rules 3, 4, 8–11 and §8).

### 6.2 Both-path / forbidden-path test matrix

Tests live in `tests/unit/core/config/test_phase2_config_validation.py` (existing pattern); a thin wrapper in `tests/unit/switches/` is added **only** for a genuinely toggleable value. No fake quality switch is invented.

| Key / area | Allowed path | Rejected path | Expectation |
| --- | --- | --- | --- |
| `kpi.codes` | exact closed ten | missing, extra, unknown code | fail loud |
| `kpi.budget_vs_actual_match` | `strict` | any other value | fail loud |
| `kpi.tolerances[*].kind` | four kinds above | unknown kind, missing/extra fields | fail loud |
| `kpi.page_size_default` / `kpi.page_size_max` | positive ints, default ≤ max | zero, negative, default > max | fail loud |
| `kpi.rebuild_batch_size` | positive int (10) | zero, negative, non-int | fail loud |
| `charts.specs[*].chart_type` | three closed values | `breakdown_pie`, unknown | fail loud |
| `charts.export_formats` | `[png, pdf]` subset | unknown format | fail loud |
| `kpi.rebuild_priority` | `rebuilds`, `background` | live/upload rank | fail loud + ordering assertion |
| `dashboard.auto_refresh_seconds` | 5–300 | <5, >300, non-int | fail loud |
| `dashboard.default_layout` | resolvable ids, `full|half` | unknown id/span, duplicate | fail loud |
| `dashboard.staleness_badge_enabled` | `true` | `false` | fail loud |
| `web.vercel.sync_enabled` | `true` | `false` | fail loud |
| `web.vercel.preview_api_target` | `mock` | `staging`, `production`, unknown | fail loud |
| `web.vercel.log_forwarding_enabled` | `true` | `false` | fail loud |
| `golden_set.tolerances_file` | absent | present | fail loud / schema forbid |
| any future legitimate toggle | both values tested | either path missing | `tests/unit/switches/` + coverage map |

---

## 7. Permissions matrix

### 7.1 Additions to `config/permissions.yaml`

Add to each role's existing `role_actions`; **do not** change the six Phase 1 categories, add no `kpi` category and no new top-level section.

| Role | `dashboard_view` | `dashboard_edit_layout` | `chart_export` | `kpi_view` | `kpi_export` | `document_purge` |
| --- | --- | --- | --- | --- | --- | --- |
| `executive_leadership` | yes | yes | yes | yes | yes | no |
| `corporate_finance_planners` | yes | yes | yes | yes | yes | **yes** |
| `audit_compliance` | yes | no | yes | yes | yes | no |
| `system_admin` | no | no | no | no | no | no |

- "Read-only" for Audit means only layout editing is withheld; export is read-shaped and cannot widen access. System Admin is denied all financial content (R24).
- `document_purge` is the dedicated permanent-purge action settled here: the as-built purge guard uses a hard-coded privileged-role list (`system_admin`, `executive_leadership`, `audit_compliance`) that does **not** match the upload-capable roles shown in the prototype, so the existing `delete` category action does not cover permanent purge. Implementation must add `document_purge` for planners only, replace the hard-coded privileged check with the permission-policy action check, and keep the drawn confirmation/toast. No other role gets it. This is the only Phase 2 permissions addition beyond ADR-0012's five actions.

### 7.2 Action surface and enforcement

- Add `dashboard_view`, `dashboard_edit_layout`, `chart_export`, `kpi_view`, `kpi_export` and `document_purge` to `core/types.Action` and the web `PermissionAction` union; update `tests/security/test_permissions.py` and the hard-coded matrix/action validation. Regenerate `docs/openapi.json` and `web/src/generated/api.d.ts` if the enum is published in the schema.
- One shared permission dependency is invoked at the start of every dashboard/chart handler (§4.5), before data access; each handler re-checks the action and filters its own content. Client-side hiding is presentation only. No wildcard, no default, no BFF middleware layer.
- KPI visibility is derived from the cited source document's `DocumentCategory` and the role's `access_scope`, the same rule `AuthorizeStep` applies today — not from a KPI category column.
- No dashboard/chart cache. Answer cache key and role cache behaviour are unchanged.

---

## 8. Golden set and release gates

- Generate one Phase 2 file under `tests/golden/questions/` (path from `golden_set.kpi_questions_path`) with `scripts/fixture_builder`, beside the untouched 163 Phase 1 questions. Never hand-edit generated files; Phase 1 ids stay permanent.
- **At least 20 numeric answer questions** covering all ten KPI codes and all three chart types. Additional tagged contract cases (not counted toward the 20) cover: chart payload and export metadata; layout default-on-miss with no write, first save, stale-save 409 with current layout, role-filtered ids; fingerprint stability for identical recomputes and change on document version, rule version, value, status, citation and conflict; `Updating` injection and precedence; and role filtering of rows, points, citations, layouts and fingerprint entries.
- Question schema stays `version: 1` with additive optional fields only: `kpi_code`, `chart_id`, `chart_type`, expected computation status and display label, expected export metadata, layout/fingerprint scenario. Answer prose is never compared. Machine fields are the expected answer: exact decimal strings, `null` with reason on `needs_review`, absence of placeholders/counts for hidden series.
- Tolerances come only from `kpi.tolerances` (§6): currency KPIs `max(0.5% of expected, 1000 in that currency)` with no conversion; margins ±0.25 percentage points; `burn_rate`/`runway` ±5%; `dso`/`dpo` ±3 days; `budget_vs_actual` exact match or `needs_review`. A `needs_review` case passes only with `value: null`, that status and its display label.
- Baselines are committed on the **first Phase 2 implementation run** under both pilot and standard; that run activates the blocking gate. A missing or unreadable baseline fails; drift tolerance stays `0.0`; baseline updates require a reviewed PR in the same change as the intended score change.
- CI runs the programmatic `run_golden()` path (not just the pytest harness self-tests) for every Phase 1+2 question under pilot and standard on PRs and main. The `v*` release/deploy workflow depends on a green main golden run. Live-provider nightly/manual runs stay informational; wire or remove the inert `LIVE_PROVIDER` flag so it cannot be mistaken for a gate.
- Pass criteria per config, never averaged: Phase 2 KPI answers and `needs_review`/no-answer/access-denied cases 100% within tolerance; Phase 1 numeric ≥95%; citations 1.0; answer coverage 1.0; ≥100 total questions, ≥20 numeric, ≥10 insufficient-data cases; no per-config score or question-count drop; no failing chart/layout/fingerprint/RBAC case. Hitherto unchecked `answer_coverage`, `minimum_numeric_questions` and `minimum_insufficient_cases` thresholds are enforced.
- Export checks stop at the response: UTC `generated_at`, company name, opaque identifier, period range, currency, units, source list and opaque filenames with no company data. Rendering acceptance is §5, not a server renderer.

---

## 9. Vercel deployment

- **Target:** Next.js frontend on Vercel Hobby at apex `finsight.sahcreatives.com` with Vercel-managed HTTPS. Production API is `https://api.finsight.sahcreatives.com` (live AWS Lambda/API Gateway; raw `execute-api` URL until the owner-corrected CNAME resolves) with production Cognito config and `finsight-prod-sessions`. Hobby limits accepted: non-commercial use, ≤10 concurrent function executions, ≤300 s functions. Pro triggers (commercial use, more concurrency/duration, Log Drains, usage API, password-protected previews) are runbook decisions, not config switches.
- **Deploy path:** `git.deploymentEnabled.main: false`; a merge-to-main workflow first runs `uv run python scripts/sync_vercel_env.py --environment prod`, then triggers a Deploy Hook (treat the hook URL as a secret). PR/branch previews stay auto-enabled. Every code-only merge also performs the idempotent sync.
- **Sync contract:** read a dedicated `/finsight/prod/web/` SSM path containing **exactly eight** non-secret values — `BACKEND_API_URL`, `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `AWS_REGION` (pinned), `SESSION_STORE`, `SESSION_TABLE_NAME`, `SESSION_COOKIE_SECURE`. Timeouts, cookie name, refresh-ahead and token-days keep existing `server-config.ts` defaults. Missing/empty allow-listed key or any unexpected key fails loudly; no model key, database password or Textract key enters Vercel. Values are readable encrypted **Config** variables (compensation requires readback); writes are serialized with backoff on concurrent-update errors, batched, and any failure restores the preflight snapshot, blocks redeploy and alerts. A daily workflow repeats the same idempotent sync; no credential generation or rotation.
- **Never-log and forwarding:** `config/never_log.yaml` is the one deny-list for Python backend and web BFF. The BFF emits only the eight allow-listed ticket fields (`request_id`, `user_id_hash`, `company_id_hash`, `role`, `endpoint`, `status_code`, `latency_ms`, `cache_hit`); hashed ids allowed, raw company ids not. Three enforcement levels: static vitest scan of log call sites, runtime throw on a forbidden key in dev/test, and a synthetic canary proving question text, document content and company data never appear in an emitted record. Static scanning alone is not sufficient. Log-redaction audit (R16) stays out of scope.
- **Log forwarding:** web BFF exchanges the Vercel OIDC token via `sts:AssumeRoleWithWebIdentity` inside the handler, SigV4-signs the OTLP POST to CloudWatch Logs and writes to `/aws/finsight/web-prod` with `logs:PutLogEvents`/`logs:CreateLogStream` only on that group. Retention comes from `web.vercel.log_retention_days` (30). Delivery is non-blocking with bounded retries; repeated failures alarm. This extends ADR-0006; Hobby's one-hour runtime logs are not the retention source.
- **Previews:** mock-only (`web.vercel.preview_api_target: mock`) in both configs; no staging API exists. Add a narrow BFF mock adapter returning deterministic canned responses (health, current-user, documents list, kpis, charts, dashboard fingerprints) with no real company data. A production build with `mock` fails the build; previews never receive the production `BACKEND_API_URL`. Use Vercel Standard Protection and production-scoped variables; CI asserts via the API (without printing values) that no allow-listed key is scoped to preview with a production value. Previews run build plus smoke/a11y checks only; manual screen acceptance stays local per §5.
- **Rollback:** Vercel promotion restores the previous deployment; because promotion does not revert env vars, a bad sync is rolled back by re-running the script against last-known-good SSM values. Implement a runbook covering both paths, the Deploy Hook secret, the OIDC trust and the Pro triggers, and link it from this section in the same PR. Inherited owner gates: custom-domain CNAME correction and pending LLM provider keys in SSM (`/ask` returns the graceful `insufficient_data` envelope until keys land).

---

## 10. Observability

- **Spans** use the ADR-0007 standard attribute set (`step`, `company`, `duration`, `active_switch_values`, `model_name`, `retry_count`, `cache_hit`, `queue_wait`, `company_hash`) through `TracingPort`. Raw company ids, KPI values, question text and document content never appear as attributes; redaction applies to every set.
  - `kpi.compute` — one per company/document-version materialisation; attributes include document version id, affected code count, `computation_rule_version` and delta mode from config, no figures.
  - `kpi.recompute.event` — after-commit outbox publish; event id, code count, best-effort outcome.
  - `kpi.rebuild.company` — one per company in a rolling rebuild; batch id, target rule version, outcome.
  - `chart.series` and `export.metadata` — server-side construction of the §4.2 response; chart id, override count, status counts, no values.
  - `chart.render` and `export.render` — browser spans forwarded through the §9 BFF OTLP path using only the eight allow-listed fields (`step` in `endpoint`, duration in `latency_ms`), correlated by `request_id`; no chart values or company data.
  - Existing `http_request` root span already correlates every API route with downstream spans; no new trace shape.
- **Metering:** KPI computation, chart/series building, export metadata and browser rendering are code or local operations, so they emit spans but **no metering row**. One usage row per paid call (LLM, embedding, rerank) remains the rule via the existing decorators; the Settings Cost view (§5.1) reads those rows. If a paid server-side renderer is ever introduced, it must add a metered decorator and its usage row in the same PR — and that is a spec change, not an implementation choice.
- **Dashboard latency alarm:** add `observability.alerts.dashboard_latency_ms` (positive int, initially 2000 in both pilot and standard) as an additive field of the existing `AlertConfig`/CDK alert-threshold pattern — not a switch and with no off path. A CloudWatch metric filter on `http_request` spans for `/kpis`, `/charts/*` and `/dashboard/*` extracts `duration`; the alarm fires when it exceeds the configured value (300 s period, one evaluation period) and joins the existing dashboard of five §15 alarms. Validate the new key in the config module; no hard-coded threshold in CDK or application code.

---

## 11. Risks addressed

| Risk | How this spec resolves it |
| --- | --- |
| [R11 — numbers and scan accuracy](../project_requirement/finsight_known_risks.md) | §2/§3: all KPI values computed by pure code from Metrics with currency, units, period and citations; no model maths; `needs_review` on missing units/inputs; §8: per-KPI tolerances and 100% Phase 2 numeric gate. |
| [R14 — DB connections and parallel steps](../project_requirement/finsight_known_risks.md) | §3.1/§3.6: KPI work joins the existing ingestion transaction; rebuilds run at `rebuilds`/`background` priority below live questions/uploads under fair-share limits; no new connection pool. §8/§10 load and latency checks cover the 50-upload/20-reader case. |
| [R15 — cost can run away](../project_requirement/finsight_known_risks.md) | §10: no new paid call, no duplicate metering rows; §5.1 Cost view reads usage rows; §9 Vercel cost dashboard and Hobby concurrency limits. |
| [R24 — role permissions](../project_requirement/finsight_known_risks.md) | §7: five dashboard/chart actions plus `document_purge`, per-role matrix, two-layer enforcement, System Admin denial, role table tests and direct-API tests. |
| [R25 — company partition](../project_requirement/finsight_known_risks.md) | §3.2/§3.4: every KPI and layout row is keyed by `company_id`, uses the existing company partition and row-level rule as second lock; no query without a company filter. |
| [R26 — chunking and parsing choices](../project_requirement/finsight_known_risks.md) | §2/§3.1: Metrics keep table/page provenance, currency, units and period; table-aware extraction and existing chunking config are reused; missing metadata is `needs_review`, never a guessed conversion. |
| [R28 — update cascade and conflicts](../project_requirement/finsight_known_risks.md) | §3.1/§3.5: delta recompute, after-commit event, final > newer, both cited conflict rows, supersession, old versions viewable, staleness badge and retention-based purge. |
| [R29 — ACID vs BASE](../project_requirement/finsight_known_risks.md) | §3.1/§3.2/§3.6: KPI rows commit atomically with the document version; the event is a best-effort hint only; fingerprint is derived, never stored; rebuilds are idempotent with no `DELETE`-before-recompute; kill-and-rerun tests required. |

R2 (customer-managed keys), R16 (log-redaction audit) and residency escalation remain outside this effort as recorded in the parent map and deviations addendum.

---

## 12. Dependencies on Phase 1 components reused

- **Ingestion pipeline and change-event cascade** — existing steps, transaction boundary, document versions, Metrics, document stamp, chunk/vector writes and delta tracking; new KPI step and after-commit outbox extend them (`application/ingest_document/`, `domain/value_objects/change_event_type.py`).
- **Postgres/Neon repository layer** — existing ports, company partition, row-level isolation and `switches.vector_store` selection; new KPI/layout repositories and migrations follow the same pattern. Aurora on the standard path is provisioned, not Serverless v2.
- **Cognito auth and current-user surface** — ASGI-scope claims, BFF session cookie, `current_user` permissions/actions, `PermissionPolicy` and `config/permissions.yaml`; no new identity mechanism.
- **Config module** — `core/config` typed models, `schema.yaml`, per-env overlays, `validate_binding_rules()`, startup logging and trace tags; all Phase 2 keys arrive only through it.
- **Metering and tracing** — `MeteredLLM`/`MeteredEmbedding`/`MeteredReranker`, `TracingPort`, ADR-0007 span schema, ADR-0006 OTLP-to-CloudWatch and the five existing alarms.
- **Answer cache and source viewer** — cache key and invalidation unchanged; source-viewer GET handlers must be mounted as the §5.3 prerequisite.
- **Web shell, tokens and messages** — prototype tokens, `web/src/lib/messages.ts`, BFF proxy and generated API client; new screens reuse them.
- **OpenAPI contract check and CI** — `docs/openapi.json`, `web/src/generated/api.d.ts`, `scripts/check_openapi.py`, `make preflight`, `make lint`, `make typecheck`, `make docs-check`.

---

## 13. Deviations addendum reference

Read [docs/plans/phase1/phase1_as_built_deviations.md](../phase1/phase1_as_built_deviations.md) before implementing anything. It is the as-built truth and explicitly requires this link. Key baseline facts this spec builds on:

- Pilot database is **Neon with pgvector**; Aurora is provisioned-only and undeployed in the pilot (§3.5 reconciliation).
- Infra switches live under `switches.*`: `vector_store`, `secrets_provider`, `observability_backend`, plus `llm_transport`.
- `upload_types` is only `new`/`update`; delete/restore/purge are document-library actions via `POST /documents`.
- Source-viewer GET handlers are not mounted; `/status` is not mounted; the live OpenAPI artifact is `docs/openapi.json`.
- Production backend is deployed; staging/dev are not; the Vercel frontend is not deployed.
- The prototype lives at `prototype/`, and as-built `/sign-in` plus System Admin denial on Documents win over prototype text.

Parent plans are not edited to match code. If a parent plan, ADR, UI standard and this addendum disagree, stop and escalate per `AGENTS.md`.

---

## Appendix A — Decision provenance

| Ticket | Decision consumed here |
| --- | --- |
| [#346](https://github.com/sah-automation/finsight-AI/issues/346) | Vercel Hobby controls → §9 |
| [#347](https://github.com/sah-automation/finsight-AI/issues/347) | Recharts v3 + Tremor, client export, a11y tooling → §5 |
| [#348](https://github.com/sah-automation/finsight-AI/issues/348) | Neon sizing, no monthly partition, batched upserts → §3.2 |
| [#349](https://github.com/sah-automation/finsight-AI/issues/349) | Binding prototype deliverable → §5 |
| [#350](https://github.com/sah-automation/finsight-AI/issues/350) | As-built deviations addendum → §13 |
| [#351](https://github.com/sah-automation/finsight-AI/issues/351) / [ADR-0008](../../adr/0008-kpi-domain-model.md) | KPI domain model, provenance, conflicts → §2 |
| [#352](https://github.com/sah-automation/finsight-AI/issues/352) / [ADR-0009](../../adr/0009-kpi-materialisation-and-rebuild.md) | Materialisation, key, estimation, rebuild → §3.1, §3.2, §3.6 |
| [#353](https://github.com/sah-automation/finsight-AI/issues/353) / [ADR-0010](../../adr/0010-metrics-api-chart-and-export-contract.md) | Metrics API, chart and export contract → §4 |
| [#354](https://github.com/sah-automation/finsight-AI/issues/354) / [ADR-0011](../../adr/0011-dashboard-layout-and-staleness.md) | Layouts, fingerprints, update cascade → §3.4, §3.5, §4.4 |
| [#355](https://github.com/sah-automation/finsight-AI/issues/355) / [ADR-0012](../../adr/0012-dashboard-chart-rbac.md) | Five actions, source-viewer filtering, no cache → §4.5, §7 |
| [#356](https://github.com/sah-automation/finsight-AI/issues/356) / [ADR-0013](../../adr/0013-golden-set-tolerances-and-release-gates.md) | Golden set, tolerances, gate → §8 |
| [#357](https://github.com/sah-automation/finsight-AI/issues/357) / [ADR-0014](../../adr/0014-screen-by-screen-ui-acceptance.md) | Screen acceptance, badges, a11y → §5 |
| [#358](https://github.com/sah-automation/finsight-AI/issues/358) / [ADR-0015](../../adr/0015-vercel-cutover-secrets-logging-and-previews.md) | Vercel cutover, sync, logs, previews → §9 |
| [#359 decision comment](https://github.com/sah-automation/finsight-AI/issues/359#issuecomment-7066439293) | Typed config contract, validation and forbidden paths → §6 |

## Appendix B — Implementation sequencing and definition of done

Ship in small green units; each PR states what changed, why, risk numbers, tests and rollback. Before any adapter code, write a committed failing contract/adapter test, run `pytest tests/architecture -q` after scaffolding, and run `make preflight` before the next unit.

1. Config and permissions: typed models, validators and tests (§6); enums, matrix, purge action, policy cleanup, OpenAPI/client regeneration (§7).
2. KPI store and materialisation: migrations, ports/adapters, pure computation, transaction and outbox, rebuild job (§3.1–3.2, §3.6).
3. API contracts: `kpi_current`, `/kpis`, `/charts/{chart_id}`, fingerprints, layout routes, handler filtering (§4).
4. UI: token parity harness, screens, badges/states, a11y libraries and checks, snapshots, source-viewer mounting (§5).
5. Golden set and CI/release gating, baselines on first run (§8).
6. Vercel sync script, workflows, never-log file, BFF logger/mock adapter, OIDC/IAM and runbook (§9).
7. Observability spans, metering checks and dashboard latency alarm (§10).

Definition of done: `make preflight`, `make lint`, `make typecheck`, `make docs-check`, `make config-check`, `make web-verify`, `make openapi-check`, `make test-golden` under both configs, the §5.5 a11y gate and a green main golden run all pass; every decision in Appendix A is reflected with no unresolved placeholder; the deviations addendum is updated in the same PR where as-built behaviour changes.
