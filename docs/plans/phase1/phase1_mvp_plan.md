# FinSight AI - MVP (Phase 1) Plan: Ingestion + RAG Q&A + Chat UI + Source Viewer

**Parent Plan:** This is a child plan derived from `docs/plans/project_requirement/finsightAI.md` and `docs/plans/architecture/phase1/finsight_mvp_hld.svg` (Phase 1 HLD). Both must be treated as the source of truth. Do not deviate from their scope, architecture, flows, or requirements — only make child-level decisions and concrete implementation details here. If any proposal would conflict with the parent plan, the parent plan is authoritative. Stop and escalate instead of deviating.

## Architectural Design (Phase 1)

The diagrams below live in `docs/plans/architecture/phase1/` and are binding alongside the Phase 1 HLD. Before implementing any slice, read the diagram that covers it; the HLD is the overall map and these are the detail zooms. Treat all of them as authoritative — no deviation without clearance.

| Artifact | Covers | When to read |
|---|---|---|
| `finsight_mvp_hld.svg` | Overall Phase 1 high-level design: upload, ingestion, Q&A, citations, source viewer, infrastructure. | Always first; map for every slice. |
| `finsight_company_isolation.svg` | How one company's data is kept separate: per-company Aurora partition, row-level rules second lock, company id on every call. | Tenancy + onboarding slice; any data access. |
| `document_lifecycle.svg` | Document/DocumentVersion states and transitions (received -> stored -> processing -> committed/failed/needs_review, superseded, rejected) plus retention. | Ingestion, updates, delete, reprocess. |
| `journey_signup_company.svg` | Signing up a company: tenancy + partition creation before any upload; upload blocked until onboarding succeeds. | Onboarding slice. |
| `journey_upload_document.svg` | Uploading a document: strict form, tenant/duplicate gates, virus scan, idempotent Step Functions pipeline, transactional commit. | Ingestion slice. |
| `journey_ask_question.svg` | Asking a question: chat question in, cited answer out; numbers from code only; insufficient data path. | Q&A backend slice. |
| `journey_open_citation.svg` | Opening a citation: fetch + render cited page/table; access re-checked on every fetch; citation id alone is never enough. | Source viewer slice. |

If a diagram and this plan disagree, the diagram (and the parent HLD) is authoritative; stop and escalate.

## Phase 1 Goal

Document ingestion + RAG Q&A with citations. This includes a simple chat screen for users to ask questions, as well as a source viewer to allow them to verify the citations that are returned.

All numerical calculations must be done by code, not by the LLM, whilst still adhering to every rule within `CODING_STANDARDS.md`.


## Recorded Decisions (2026-10-26)

These refine the parent plan. Where a decision resolves a conflict between authoritative documents, the reason is recorded here so it is not "fixed" later.

| # | Decision | Choice |
|---|---|---|
| D1 | Company data separation | One Aurora per cell. Shared tables with a native partition per company for documents, chunks, vectors and metrics. Row-level rules as a second lock. No schema-per-company. |
| D2 | Job state | Aurora is the source of truth and updates job status in the same transaction as the document. DynamoDB holds a rebuildable progress view plus sessions, chat history, answer cache, role cache and role version. |
| D3 | Background uploads | Raw file -> S3 -> SQS -> Step Functions, one worker per step. Retries and a dead-letter queue after `job_max_receive_count`; every step is safe to repeat. |
| D4 | File readers | One reader interface for pdfplumber, Textract, Tesseract, Excel, CSV and DOCX, plus the page router and table reader. Build the free readers first; Textract must exist and be tested before pilot config switches to it. |
| D5 | Updates and versions | Every update creates a new version. Hash pages and use stable chunk ids; embed only changed chunks. Answers cite the latest final version. Keep versions for `version_retention_days` (365) and soft-delete for `deleted_retention_days` (30). The document stamp changes in the same transaction. |
| D6 | Phase 1 scope | Ingestion, Q&A with citations, source viewer, and the onboarding/partition gate. Store numbers found during ingestion because the HLD save step includes them. No metrics store, dashboards, forecasts, alerts, recommendations or multi-agent work; those wait for Phases 2 and 3. |
| D7 | Quality and access bar | 95% numeric accuracy on the 100+ question set, the parent latency targets, and Cognito login with the four roles enforced from `permissions.yaml` in Phase 1. |
| D8 | Login provider | **AWS Cognito (Lite tier), confirmed 2026-10-26.** Groups map to the four roles in `permissions.yaml`. No third-party identity vendor. Corporate SSO (SAML/OIDC) is supported but the free tier is 50 federated users/month, so it is out of pilot scope. |
| D9 | Model providers | **Confirmed 2026-10-26:** Gemini is primary (answers) and provides embeddings; Groq is the cheap/fast path for simple lookups; NVIDIA NIM is the fallback and the reranker. No Anthropic, OpenAI or Titan keys exist. Model IDs and rate limits live in config, never in code. |

**Consequences**

- `migrations/versions/0001_initial_schema.py` currently creates plain shared tables with no partitions, no row-level rules, no versions, no page hashes and no stamp. The tenancy slice replaces or extends it before any ingestion work.
- D2 settles the HLD ("jobs in DynamoDB") versus the config guide ("job status in Aurora, same transaction"). Keep both: Aurora is the truth, DynamoDB is disposable.
- D6 is the clearance for `application/onboarding`, which the HLD implies through "partition per company" but does not draw as a flow.
- D6 removes `Recommendation` from Phase 1. `Metric` stays only as an extracted figure saved during ingestion; there is no metrics use case or dashboard.
- D7 makes the golden set, login and the performance targets Phase 1 gates, not later work.
- D9 replaces the placeholder providers in `config/schema.yaml` (Anthropic, OpenAI, Titan, Cohere) when the model gateway is built. Until then, config validation still describes providers we cannot call.
- **Residency cleared 2026-10-26:** the pilot company is US-based, so `us` region hosting satisfies the parent in-country rule. This does not generalise: an India-based company would need India hosting or written clearance.

## Current Repo State (2026-10-26)

The checkboxes below describe the target state; not every unchecked item is unbuilt. Already present:

- `core/config` (loader, models, YAML validation), `core/errors`, `core/logging`, `core/types`
- `domain/services` (`cache_key`, `evidence`, `permission_policy`)
- architecture and security test suites
- initial Alembic migration (plain tables, no partitions/RLS yet)
- CDK scaffold and environment config

Still to build: partitioned schema + RLS, all ports and adapters, application use cases, API, UI, Step Functions workflow, DynamoDB progress view, Cognito wiring, golden runner.


---


## Build Order (Inside Out)

We must build from the inside out to enforce the dependency direction (`entrypoints -> application -> domain <- adapters`). The layer order below defines where code belongs; the slice order under "Suggested Implementation Order" defines when to build it.


### 1) Foundation (Core) - Do First
Establish all shared blocks that everything else will rely on.

- [x] **core/config** - The *only* place to read environment variables and config files. Must be typed, frozen, validated at startup and fail loudly (Enforce every validation rule from the Config Switch Guide).
- [x] **core/errors** - `UserFacingError`, `RetryableError`, `PolicyBlocked`, `InsufficientData`, and any other errors that need to be mapped at the entrypoint level.
- [x] **core/logging** - Structured logging with trace IDs. Absolutely no question text, chunk text, PII or answers within logs.
- [x] **core/types** - Shared IDs and enums (`CompanyId`, `Role`, `DocumentId`, `ChunkId`, `CitationId`, `JobId`, etc.)
- [x] **core/constants** - Only constants that are truly constant. Everything else must go into config.



### 2) Domain Layer - Pure Business Logic
No vendor, AWS, HTTP or UI imports. This is the heart of the application.

- [x] **domain/value_objects** - `Money` (Decimal only), `Period`, `Citation` (must contain enough locator information for the source viewer, including the cited document version, not just latest), `Confidence`. All immutable.
- [ ] **domain/entities** - States are tracked per `DocumentVersion`. Allowed states: `received`, `stored`, `processing`, `committed`/`done` (ready for citations), `failed` (terminal after retries/DLQ or worker timeout), `needs_review` (split into chunk-level and whole-document), `superseded`, `rejected` (virus scan failed). Transitions: `received` -> `stored` | `rejected`; `stored` -> `processing`; `processing` -> `committed` (chunk-level needs_review may still commit but flag chunks), `processing` -> `needs_review` (chunk-level or whole-document), `processing` -> `failed` (step error, retries exhausted after `job_max_receive_count`, or heartbeat/worker timeout). Whole-document `needs_review` does not commit (no visible chunks/vectors). On commit of a new version, the previous version becomes `superseded` (kept for `version_retention_days`, old answers/citations remain valid). Exit from `needs_review` is only by uploading a corrected file as an `Update` (no in-app reviewer in Phase 1). `DocumentVersion`, `Chunk` (stable chunk ids), `Metric` (extracted figures only), `Answer`. No `Recommendation` in Phase 1 (D6). Enforce transitions, versioning and soft delete.
- [ ] **domain/ports** - Interfaces for every external dependency. Examples: `DocumentReader`, `LLMGateway`, `EmbeddingProvider`, `VectorSearch`, `VectorWrite`, `HybridSearch`, `Reranker`, `ObjectStorage`, `DocumentRepository`, `ChunkRepository`, `JobRepository`, `AuditLog`, `PartitionManager`, `AnswerCache`, `RoleCache`, `VirusScanner`, `UnitOfWork`, `Metering`. Every data access method must require `company_id`.
- [x] **domain/services** - `InputGate` (PII + prompt-injection checks), `EvidenceChecker`, `CitationChecker`, `OutputGate`, conflict resolution, `DeltaDiffer`, `DocumentStamp`, and any other pure business rules.



### 3) Application Layer - Use Cases
Orchestrate the domain and ports. No adapter imports, only domain.

- [ ] **application/onboarding** - Child-level addition approved by D6. Responsible for creating a company's partition (tables/indexes/vector indexes) before the first upload. Must be idempotent via `request_key` (retries return the same company), transaction safe (company stays `incomplete` until the final commit, `ready` only as the last step), auditable, validate the requested region against the approved list, allow email verification to complete after company creation, and block uploads until completed. Surface setting-up/ready status and clear, non-leaking errors to the admin.
- [ ] **application/ingest_document** - Pipeline of steps (validate upload form, classify, read via page router, parse, chunk by structure, delta diff against previous version, embed, store, update the document stamp, clear cache). After file lands, run virus scan: on failure set version state to `rejected` (never queued/stored), on success proceed to `stored` and enqueue. Track state per version; chunk-level `needs_review` allows commit but flags chunks and excludes them from numbers/citations; whole-document `needs_review` does not commit (no visible chunks/vectors). Enforce heartbeat/worker timeout -> `failed` (terminal after retries/DLQ). Must fully implement delta tracking and versioning.
- [ ] **application/delete_document** - Soft delete, clear the answer cache, remove chunks, vectors and metrics after `deleted_retention_days`, and keep the audit entry. Must be idempotent.
- [ ] **application/reprocess** - Rolling reprocess after a chunking or embedding change. Lower priority than live questions, a few companies at a time, and safe to repeat without duplicate chunks. The document stays on the current done version until the new reprocessed version commits atomically in one transaction; old and new vectors/chunks are never mixed. On commit, the old version becomes `superseded`. Chunk ids remain stable where unchanged.
- [ ] **application/ask_question** - Q&A flow (input gate, answer cache, waiting line, understand, hybrid search, rerank, "calculate with code", evidence gate, model router, generate answer, verify citations via OutputGate, stream). Must enforce "numbers from code only", company isolation and must return fully populated `Citation` objects, or `InsufficientData` instead of guessing.
- [ ] **application/source_viewer** - Fetch the cited (answer-time) version of a source. Validate company, role and access scope, and return a renderable citation page/table. Read from storage/repositories before signing S3; sign an S3 link only for "view original file". Handle no-access, removed/unavailable and temporary-failure states with one non-leaking 'not available' response, including denied attempts in the audit, never log signed links, and show 'a newer version exists' when applicable plus a 'needs review' badge for flagged chunks. This is critical to prevent cross-company data leakage.
- [ ] **application/shared** - Step interfaces, contexts (`RequestContext` with company/user/role/access scope), the `UnitOfWork` transaction boundary, and shared helpers.



### 4) Adapters Layer - Vendor Implementations
Implement all ports. For Phase 1, we are building *all* of the readers and the ability to route between them. The "pilot" will just disable the expensive ones via config, we are not stubbing out their implementations.

- [ ] **adapters/readers/** - Implement a `BaseReader` interface with a common return shape (`text`, `tables`, `page_numbers`, `confidence`). Implement the following:
   - `PdfPlumberReader` (text + tables for born digital PDFs)
   - `TextractReader` (paid scan OCR and table extraction; async StartDocumentAnalysis, in-region only)
   - `TesseractReader` (free OCR for scanned PDFs/images) - must be wired and testable, togglable via `scan_reader`
   - `TableReader` (table and layout pages used by the router; pdfplumber or Textract per `table_reader`)
   - `ExcelReader` (xlsx/xls) via `openpyxl`/`pandas` preserving sheets, headers, units
   - `CsvReader` (csv/tsv) with delimiter detection and header preservation
   - `DocxReader` (docx) preserving paragraphs, tables, lists
- [ ] **adapters/queue** - SQS queueing plus Step Functions task dispatch, retry list and dead-letter handling. Every job is keyed by job id and safe to repeat.
- [ ] **adapters/auth** - Cognito login and authorizer mapping to `RequestContext`; role lookup and role-version cache behaviour from config.
- [ ] **adapters/security** - Virus scanning at upload (HLD input gate); rejects before the file is queued.
- [ ] **adapters/readers/router.py** - `PageRouter` that inspects each page (or file) and routes to `table_reader` for table/layout heavy pages, `reader` for text, and `scan_reader` if OCR is required. Both routed and non-routed paths must be implemented and tested.
- [ ] **adapters/embedding** - Google Gemini embeddings behind the port (D9), with retry logic from config.
- [ ] **adapters/vector_store** - `aurora_pgvector` implementation of `VectorSearch`/`VectorWrite` plus hybrid keyword search (Postgres full text) behind one search interface. Must enforce `company_id` first and target the correct per-company partition.
- [ ] **adapters/llm** - LiteLLM gateway, router (cheap/primary), fallbacks, timeouts, first-token timeout and backup request as per config. Pilot providers: Groq, Google Gemini and NVIDIA NIM.
- [ ] **adapters/rerank** - Cross-encoder fallback to search order on failure, backed by NVIDIA NIM (D9).
- [ ] **adapters/repositories** - Postgres repositories for companies, documents, versions, pages, chunks, metrics (extracted figures), jobs, audit logs and partition metadata. Every method requires `company_id`. Partition aware (queries must target the correct company partition).
- [ ] **adapters/partitions** - `PartitionManager` implementation to create/drop partitions, indexes and per-partition vector indexes, and record partition metadata. Must be callable by the onboarding use case and be idempotent.
- [ ] **adapters/storage** - S3 for raw files (needed to re-render or serve original pages for the source viewer), one folder per company, KMS encryption, and pre-signed upload links.
- [ ] **adapters/cache** - DynamoDB answer cache with the exact key (company + role + access scope + question + document stamp), role cache/version, and the rebuildable job-progress view from D2. Clear answers on upload, update and delete; read the stamp strongly consistent.
- [ ] **adapters/metering** - Decorator based metering for every paid call (model, embedding, rerank, Textract and Lambda run time).



### 5) Entrypoints, UI & Composition - Wire Everything Together
Thin doors, no business logic. Composition root is the only place that instantiates concrete classes.

#### API (Backend)
- [x] **composition/** - Wire pilot and standard sets based off of config. Apply DI to every use case (No `new` inside of application/domain). Construct the reader registry (all readers) and the Step Functions worker set regardless of pilot settings. Wire Aurora, DynamoDB, S3, SQS, Cognito and metering.
- [ ] **entrypoints/api/contract** - Publish an OpenAPI contract for onboarding, upload, status, question (streaming) and source viewer; generate the UI client from it.
- [ ] **entrypoints/api/onboarding** - Internal/admin endpoint or job trigger to run onboarding for a company (create partitions). This *must* be able to run prior to any upload, accept a `request_key` for safe retries, validate region/company-form inputs before submit, surface setting-up/ready status and clear error messages, keep email verification non-blocking, and mark the company ready only after the final commit.
- [ ] **entrypoints/api/upload** - Upload endpoint. Returns a pre-signed S3 upload link. After the file lands, run the virus scan and only then queue the job. If virus scan fails, set the document version to `rejected` (terminal, never enqueued/stored as visible content). Must accept and validate: `company_id`, `document_category` (from `documents.categories`), `period` (e.g `YYYY-QX` or `YYYY-MM`), `status` (`draft` | `final`), `upload_type` (`new` | `update`), `replaces_document_id` (required if `update`), and the file(s). Enforce duplicate check, metadata validation, and reject upload if partition does not exist. Whole-document `needs_review` results in no visible chunks/vectors and does not commit until fixed (exit only via corrected file as an Update). Upload no longer handles delete; document lifecycle is managed through the document library endpoints below.
- [ ] **entrypoints/api/documents** - Document library and lifecycle endpoints: list/search documents by company/category/period/owner/date/status; get document metadata; soft delete a document to the recycle bin; restore within `deleted_retention_days`; permanent purge (privileged, audited); read recycle bin contents. All operations enforce company, role and access scope, and take effect immediately on retrieval and the answer cache.
- [ ] **entrypoints/api/status** - Ingestion/job status (by job id and document id). Aurora is the truth; show progress and queue place from the DynamoDB view.
- [ ] **entrypoints/api/question** - Chat question endpoint. Build `RequestContext` from the Cognito authorizer (with role check), call `ask_question` and stream the answer with citations.
- [ ] **entrypoints/api/source_viewer** - Source retrieval endpoint (e.g `GET /source` or `GET /documents/{id}/citations/{citation_id}/source`). Must authorize against the citation (validate company + role + access scope), call `source_viewer` use case and return the renderable source (original text, table HTML/JSON, page number, document name and highlight info). Never leak data from other companies.
- [ ] **entrypoints/workers/** - One Step Functions handler per ingestion step (read, delta, chunk, embed, save, cascade) plus SQS/DLQ handling. Never a single "do everything" worker.



#### UI (Frontend) - Simple Chat + Source Viewer
As this is a web based platform, we need a minimal Next.js UI to satisfy the "Q&A with citations" requirement.

- [ ] **Upload Form** - Explicit form fields for `Category`, `Period`, `Status` (Draft/Final), `Upload Type` (New/Update), `Replace Document` (if update), file picker with allowed extensions (PDF, XLSX, XLS, CSV, DOCX). Show duplicate warnings, validation errors and the partition-missing message from the API. No delete action appears here.
- [ ] **Document Library & Recycle Bin** - Searchable list of company documents with metadata, owner, status and retention state; row actions for View, Update, soft Delete; recycle-bin view with Restore (inside `deleted_retention_days`) and Permanent Delete (privileged, audited). Deleted items are excluded from RAG and citations immediately.
- [ ] **Chat Screen** - A simple chat interface (message thread). Allow users to type questions, show loading and streaming states, render answers, and display citations as clickable elements (e.g `[1]`, `[Doc - Page X, Table Y]`). Show "insufficient data" and "busy" clearly.
- [ ] **Source Viewer** - Either a modal, side panel or dedicated page. When a citation is clicked, fetch from the source viewer API and render the cited content (preserve tables as tables, show page number, document title, and highlight the relevant span if possible). Must respect the current user's company/role.
- [ ] **API Client** - Call the API endpoints with auth. Handle errors gracefully (e.g "insufficient data", rate limits, waking up messages, partition missing, etc).
- [ ] **Routing/Auth** - Integrate Cognito login (respecting RBAC). All requests must carry auth context to be mapped to `RequestContext`.



### 6) Config, Migrations, Infra & Tests
- [ ] **config/schema.yaml** - Enforce *every* validation rule from the Config Switch Guide (combinations, model chains, key modes, sizes, partitions, onboarding, etc). This must fail startup on invalid config.
- [x] **config/*.yaml** - `dev.yaml`, `test.yaml`, `staging.yaml`, `prod.yaml`, `permissions.yaml`, `prices.yaml`. Use pilot values to start off with. The pilot will just toggle flags, not remove code paths.
- [ ] **migrations/** - Alembic migrations for companies, users/roles, documents, document versions, pages, chunks (hashes + stable ids), vectors (pgvector), metrics (extracted figures), jobs, answer cache references, audit logs, and *partition metadata*. Must create a partition per company with its own vector index, enable row-level rules, enforce `company_id` indexes, and be able to run `upgrade`/`downgrade` across every partition. The existing `0001` is plain tables and must be extended or replaced before ingestion work starts.
- [ ] **infra/cdk/** - Leverage the existing scaffold. Add only what the pilot needs: S3, Aurora (serverless + pgvector), SQS + DLQ, Step Functions, Lambda, API Gateway, DynamoDB (progress view, answer cache, role cache) and Cognito, gated by switches. Ensure infrastructure supports creating per-company partitions/indexes as per D1.
- [x] **tests/** - Unit (domain/application with fakes), contract (one per port against every adapter - including every reader), architecture (import direction, rules), switch path (both ON/OFF), golden set (pilot config, 95% numeric accuracy), security (RBAC, company filter, cache key, cross-company isolation, RLS), partition tests (onboarding before upload, partition missing blocked), delta tracking/version/delete tests, auth tests, performance tests, and integration tests.



---


## Key Principles For This MVP

- **All readers are first class.** We build support for PDF (plumber), scanned PDF/OCR (Tesseract and Textract), table/layout pages, Excel (xlsx/xls), CSV (csv/tsv) and DOCX from the start. Pilot config may set `scan_reader` / `table_reader` to free options, however no reader code path may be missing. The page router and table reader must work with all of them.
- **Upload form is strict.** `category`, `period`, `status` (draft/final), `upload_type` (`new`/`update`) and `replaces_document_id` (for updates) are all required where applicable. The API must validate against `documents.categories` and reject unknown values. Duplicate checks (same file hash or same company/category/period/name) must suggest an update. Delete, restore and permanent purge are handled through the document library and recycle bin, not the upload form.
- **Delta tracking is enforced.** With `delta_tracking: true` (pilot default where applicable), we must hash pages and chunk ids, embed only new/changed chunks, mark removed chunks inactive, change the document stamp on update (clearing cached answers), publish a change event for Phase 2/3 consumers, and flag other documents in the same company/period as "may be affected". Other documents are never edited automatically. Old versions are kept for `version_retention_days`; delete is soft for `deleted_retention_days`, then purged. Both `delta_tracking: true` and `false` paths must be implemented and tested.
- **Partitions are required.** One Aurora per cell, shared tables partitioned per company, with row-level rules as a second lock (D1). Every company must have its partition created via the onboarding use case before its first upload is accepted. The `onboarding` service must create partitions/indexes/vector indexes, be idempotent, auditable, and the upload endpoint must block with a clear error if the partition does not exist. Partition metadata must be tracked, and all repository/vector queries must target the correct partition.
- **Scope is bounded (D6).** Phase 1 is ingestion, Q&A with citations, source viewer and the onboarding gate. No metrics store, dashboards, forecasts, alerts, recommendations or multi-agent code. Numbers found during ingestion may be stored as extracted figures; the LLM still never calculates.
- **Citations are first class.** The `Answer` entity cannot exist without citations, and answers cite the latest final document version. The output gate must block answers without valid citations, and the UI must always display them as clickable links to the source viewer.
- **Source viewer is secured.** Fetching a source must always authorize via `RequestContext` (company + role + access scope). You must never be able to fetch another company's document via a citation id alone. Opening the original file is governed by a separate, still-to-be-added view-original/download permission action that must be decided per role.
- **Numbers from code only.** Any calculated figures (margins, sums, ratios) must come from SQL/pandas in the application layer. The LLM can only cite these results, it can never compute them.
- **Architecture is enforced.** No vendor imports in domain/application, DI everywhere, ports and adapters for everything, only `core/config` reads config/env. Import-linter must pass.
- **Config driven.** No hardcoded model names, limits, timeouts or vendors. Every switch must have both paths implemented and tested.
- **Company isolation everywhere.** Every repository, vector search, cache read/write, partition access, and the source viewer must take and enforce `company_id`.
- **Access is a Phase 1 gate (D7).** Cognito login, the four business roles, and `permissions.yaml` are enforced on every request. A missing role or category permission is denied, never defaulted.



---


## Suggested Implementation Order (Pragmatic)

Build in vertical slices. Each slice ends in something runnable and keeps the dependency direction (`entrypoints -> application -> domain <- adapters`). Do not build a whole layer before proving a slice.

0. **Reconcile** - Update the checkboxes against the current repo (see Current Repo State) so working code is not rebuilt. Confirm the config schema matches every rule in the Config Switch Guide before slice 1.
1. **Tenancy + Onboarding** - Partitioned tables + RLS, partition metadata, migrations, `PartitionManager`, `application/onboarding`, onboarding endpoint, upload rejects when the partition is missing. This proves the riskiest decision first.
2. **Ingestion for one PDF (new)** - Reader port + pdfplumber reader + page router, S3 pre-signed upload, virus scan, SQS + Step Functions, job status (Aurora truth + DynamoDB view), transactional save, answer cache clear.
3. **All readers** - Textract, Tesseract, Excel, CSV, DOCX and table reader. Contract tests for every reader and both router paths.
4. **Updates, delete, reprocess** - Delta hashing, stable chunk ids, versions, retention, soft delete, stamp change, change event/cascade, rolling reprocess.
5. **Q&A backend** - Input gate, cache, waiting line, hybrid search, rerank, calculate with code, evidence gate, model router/gateway with Groq/Google/NVIDIA, output gate, streaming, "insufficient data".
6. **Source viewer backend** - Authorization (company + role + access scope), citation resolution, S3/page fetch, renderable payload.
7. **UI** - Next.js upload form, chat screen and source viewer against the OpenAPI contract; Cognito login and role-aware rendering.
8. **Hardening** - Composition root, Step Functions/DynamoDB/Cognito infrastructure, observability and metering, golden set at 95%, performance tests, and the checklist from section 17 of `CODING_STANDARDS.md`.



---


## Done When (Acceptance Criteria)

Phase 1 will be considered complete only when all of the following are true.

### Functional
- [ ] **Ingestion works for all required types** - Can upload and process PDF, scanned PDF (OCR), Excel (xlsx/xls), CSV and DOCX. Page numbers and tables are preserved.
- [ ] **Onboarding enforced** - A company without a partition cannot upload. Onboarding creates the partition successfully and is idempotent.
- [ ] **Upload flow complete** - Upload form captures category, period, status (draft/final), upload type (new/update), and handles updates via `replaces_document_id`. Duplicate check warns and suggests update. Delete, restore and permanent purge are exercised through the document library and recycle bin.
- [ ] **Delta tracking verified** - Updating a document with only changed pages/chunks only reprocesses what changed (verified by job logs/tests). Changing a document invalidates the answer cache, changes the stamp, and publishes a change event.
- [ ] **Delete and reprocess work** - Delete is soft for `deleted_retention_days` then purges chunks, vectors, metrics and cache while keeping the audit entry. Reprocess is rolling, lower priority than questions, and produces no duplicate chunks.
- [ ] **Login and roles enforced** - Cognito login maps to `RequestContext`; the four roles and `permissions.yaml` are checked on every request, including the source viewer.
- [ ] **Q&A with citations** - Can ask questions and receive answers with verifiable citations (document, page, table). Clicking a citation opens the source viewer.
- [ ] **Source viewer secure** - Source viewer only shows content from the requesting company's documents. Cross-company access attempts are blocked and tested.
- [ ] **Numbers from code only** - All calculated metrics in answers come from code (SQL/pandas). The LLM never computes numbers (verified by tests).


### Quality & Safety
- [ ] **Golden set passes** - Run the 100+ question set on pilot config with at least 95% numeric accuracy, and track the score on every release. A drop blocks the release.
- [ ] **Performance targets met** - Typical question under 15 seconds, a 50-page document under 5 minutes, and first streamed response at p95 3s / p99 5s / p99.9 7s.
- [ ] **Cross-company isolation test** - Automated test proves company A cannot see company B's documents, chunks, answers, or sources under any endpoint.
- [ ] **RBAC enforced** - Role table tested against every action and category per `permissions.yaml`. Privileged roles behave correctly.
- [ ] **Architecture enforced** - `import-linter` passes, no vendor imports in domain/application, every dependency goes through ports/adapters, only `core/config` reads env/config.
- [ ] **All switch paths tested** - Every toggleable item has tests for ON and OFF. Output gate is never disabled.
- [ ] **Contract tests pass** - One contract test per port runs against every adapter (including all six reader types).
- [ ] **Security checks pass** - Cache key test, company filter on every repo/query, no sensitive data in logs, secrets from config only.


### Operational
- [ ] **Config validation passes** - `make config-check` passes for all environments. Invalid configs fail loudly.
- [ ] **Migrations verified** - `upgrade head` -> `downgrade base` -> `upgrade head` works against the test DB, including every company partition and vector index.
- [ ] **Real sample documents processed** - At least a small set of real (anonymized) documents across all file types (PDF, scanned PDF, Excel, CSV, DOCX) have been ingested successfully and are queryable with citations.
- [ ] **Region and residency confirmed** - The pilot runs in `us` (recorded 2026-10-26). Confirm the pilot company is US-based; if it is India-based, US hosting conflicts with the parent in-country rule and needs clearance.
- [ ] **Observability works** - Every step writes a trace span, every paid call writes a usage row, and the alert list from `CODING_STANDARDS.md` section 15 is live.
- [ ] **Backup and restore tested** - Aurora, S3 and DynamoDB backups are encrypted, in-region, and a restore has been performed successfully.
- [ ] **CI green** - All gates in CI pass (lint, types, imports, arch tests, unit, contract, switch tests, integration where applicable, migrations, security, golden set at 95%, performance where practical).



---


## Need From You (Blockers / Inputs)

To avoid guessing and to be able to hit the above "done when" criteria, please provide the following:

### Where to add inputs
- **Sample documents** - `tests/fixtures/documents/` (see `README.md` there for naming, anonymization and size rules).
- **Golden set** - `tests/golden/questions/` (see `README.md` and `_template.yaml` there for the YAML shape).

### Documents & Data
- [ ] **Sample documents** - Add anonymized real documents (5-10 minimum) covering PDF, scanned PDF, Excel, CSV, and DOCX to `tests/fixtures/documents/`. Ideally include tables, multi-page statements and invoices.
- [ ] **Golden set** - Add 100+ questions with known answers and expected citations to `tests/golden/questions/` (or approve building it from the sample documents).
- [ ] **Document categories** - Confirm `documents.categories` for the pilot (if different from the example list).
- [ ] **Permissions matrix** - Confirm `config/permissions.yaml` for the 4 roles, or any changes to them.


### Infrastructure & Providers
- [x] **Region** - **US**, confirmed 2026-10-26. The pilot company is US-based, so US hosting satisfies the parent in-country rule.
- [x] **Model providers** - **Confirmed 2026-10-26:** Gemini is primary and provides embeddings, Groq is the cheap/fast path, NVIDIA NIM is the fallback and reranker (D9). Model IDs, endpoints and rate limits go in config during the model gateway slice.
- [x] **Vector store constraints** - Confirmed: `aurora_pgvector`, one partition per company with its own vector index (D1).
- [ ] **Object storage** - Proposed: one bucket per environment/region, KMS encryption, one folder per company, pre-signed upload links. Confirm any client naming standard.
- [x] **Auth** - **AWS Cognito, Lite tier, confirmed 2026-10-26** (D8). Groups carry the four roles; API Gateway authorizer maps them to `RequestContext`.


### Project Constraints
- [ ] **Team** - Team size and availability (to scope realistically).
- [ ] **Timeline** - Target dates for MVP completion/demo.
- [ ] **Budget notes** - Any hard budget caps for pilot (to set metering alerts appropriately).
- [ ] **Compliance notes** - Any additional data residency/compliance constraints beyond what's in the requirements.
