# ADR-0008: KPI values are code-computed from Metrics and keep their provenance

## Status

Accepted. Storage key refined by ADR-0009.

## Context

Phase 2 adds a structured KPI store for the ten figures named in the project statement (`docs/plans/project_requirement/finsightAI.md:37`): revenue, gross margin, net margin, operating expenses, cash flow, burn rate, runway, DSO, DPO and budget vs actual. The prototype (`prototype/dashboard.html:78-88`) and the UI standard (`UI_STANDARDS.md:451`) use the same list, so there is no open question about additional codes.

Three constraints shape the model. Numbers must be computed by code, never by the model (risk 11, `docs/plans/project_requirement/finsight_known_risks.md:347-365`). Updated documents can leave draft and final figures disagreeing, and the rule is to prefer final over draft and newer over older while showing both with citations (risk 28, `:850-874`). The pilot runs on Neon, not Aurora (`docs/plans/phase1/phase1_as_built_deviations.md:34-44`). Without a settled boundary between an extracted figure and a computed one, an implementation could let the model invent a KPI, guess a missing composite input, overwrite a conflicting row, or show a distributed monthly figure as if the source had stated it.

## Decision

- A **Metric** is a raw extracted figure with provenance, as defined in `GLOSSARY.md`. Margin inputs (cost of goods sold, net income) are stored as Metrics so code computes gross/net margin percentages. A **KPI** is a code-computed, period-bucketed series derived from one or more Metrics; the model never authors or edits its value.
- The KPI code list is closed for Phase 2: `revenue`, `gross_margin`, `net_margin`, `operating_expenses`, `cash_flow`, `burn_rate`, `runway`, `dso`, `dpo`, `budget_vs_actual`. A new code is a spec change, not an implementation choice.
- Every KPI row carries `company_id`, `kpi_code`, `period`, `currency`, `units`, `value` (exact decimal, never float), `source_citations` (an array of CitationIds), `computation_status`, `document_version_id`, `created_at` and `updated_at`. `period` is always the period declared by the source document. For `estimated` rows (quarterly-to-monthly spread), an additional `chart_period` field carries the finer charting bucket. `document_version_id` is the UUID of the exact document version the KPI was computed from.
- `computation_status` is `computed`, `estimated` or `needs_review`.
- `runway`, `dso`, `dpo` and `budget_vs_actual` are composite: if any required input Metric is missing, the row is `needs_review`. No value is guessed, borrowed from another period or company, or back-filled from a partial input set.
- `budget_vs_actual` compares a budget Metric with an actual Metric only when their source-declared `period`, `currency` and `units` match exactly. A mismatch is `needs_review`, not a converted or approximated comparison.
- When a quarterly figure is spread across months for charting, each monthly row has `period` set to the source-declared period (e.g. `2026-Q3`), is `estimated`, labelled `Estimated`, and carries `chart_period` for the month (e.g. `2026-07`, `2026-08`, `2026-09`). An `Estimated` value is never presented as a figure the source document stated.
- Conflict resolution follows risk 28: final beats draft and newer beats older for the value used, but when figures still differ both rows persist with their own citations and the chart shows both with distinguishing labels. Conflicting rows are `computed`, not `needs_review`. No conflicting row is silently overwritten.
- The storage primary key is `(company_id, kpi_code, period, document_version_id, chart_period)`, as refined by ADR-0009. `chart_period` is non-null and equals `period` for non-estimated rows; the extra component distinguishes the monthly rows of one quarterly spread. Different document versions still admit two rows for the same company, code and period when a conflict persists.
- `Draft` and `Updating` are separate display states owned by the update cascade (#354); `Estimated` is the state this ADR defines. The chart payload and export labels are owned by #353.

## Consequences

- KPI materialisation, estimation mechanics and rebuilds were settled in #352 and ADR-0009. The illustrative DDL in `research-neon-kpi-timeseries.md` is a sizing sketch; its single-row PK cannot hold conflicting rows or multiple estimated months. The canonical PK is the five-column key in ADR-0009.
- The Phase 2 API and chart/export contract (#353) must expose `computation_status`, `chart_period`, `source_citations`, `document_version_id` and the `Estimated` label.
- Dashboard treatment of Draft, Estimated and Updating, and the cascade that sets them, stay with #354.
- Phase 2 tests must cover a missing composite input, a mismatched budget/actual pair, an estimated monthly row and a final/draft conflict. No such test can pass by asserting a guessed number.
