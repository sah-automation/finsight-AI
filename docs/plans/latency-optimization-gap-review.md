# Latency Optimization Gap Review

Date: 2026-11-11
Scope: backend (`src/`) and frontend (`web/src/`) of FinSight-AI
References: `docs/plans/project_requirement/finsight_config_switches.md` (§5.10, 5.11, 5.13, 5.15, 5.16, 6), `docs/perf-baseline.md`, `docs/load-baseline.md`

## Summary

The project has the *config surface* and *switches* for advanced latency techniques, but most runtime paths are still sequential, several are N+1, and the frontend has no client-side data cache/dedup layer. A few pieces are genuinely parallel (LLM gateway backup requests), but the bulk of the hot path and ingestion path are gaps.

## What is actually used today

| Technique | Where | Evidence |
|---|---|---|
| LLM backup request / parallel primary+backup | Gateway | `src/finsight/adapters/llm/_llm_gateway_stream.py` (`_attempt_step`, `asyncio.wait`, `FIRST_COMPLETED`) |
| Concurrency cap + FIFO waiting line | Q&A entry | `AskQuestion._execute` → `self._waiting.run(...)` |
| Answer cache (DynamoDB) | Q&A | `AskQuestion._cache_step` / `_cache.set` |
| Input gate before model calls | Q&A | `_input_gate_step` |
| Delta tracking / page dedup on ingestion | Ingestion | Textract page-number dedup; chunk id hashing |
| Citation dedup | Q&A | `AskQuestion._build_citations` (`seen` set) |
| Role/session caching | Frontend auth | `getServerSession = cache(...)` in `web/src/lib/auth/server-session.ts` |
| Next.js fetch dedup | Server components | only for the auth session fetch; no data queries are server-fetched |

## Gaps found

### 1. No parallelization in the Q&A hot path despite the `parallel_steps` switch
- `AskQuestion.parallel_steps` is read from config and validated (`db_pool_size_per_function >= db_connections_per_request`), and has a dedicated switch test (`tests/unit/switches/test_parallel_steps_switch.py`), but `_heavy()` in `src/finsight/application/ask_question/ask_question.py` runs every step strictly sequentially: `_embed` → `_metrics.list_metrics` → `_calculator.calculate` → `_search.search` → `_reranker.rerank` → evidence → model. None are wrapped in `asyncio.gather`.
- Spec §5.11 promises: input gate + embedding + understand together; metrics SQL next to search/rerank; prompt build + model connection opened during rerank; rerank in `rerank_parallel_batches` batches. None implemented.
- Evidence: `grep -rn "asyncio.gather\|asyncio.TaskGroup" src` returns 0 hits in `src/`.

### 2. N+1 DB fan-out in every repository upsert
Per-entity round trips inside loops, instead of batched multi-row statements:
- `src/finsight/adapters/repositories/_postgres_chunk_repository_upsert_chunks.py` — `for chunk in chunks: await self._execute(...)` (one upsert per chunk)
- `src/finsight/adapters/repositories/_postgres_metric_repository_upsert_metrics.py` — `for metric in metrics: ...`
- `src/finsight/adapters/repositories/_postgres_document_table_repository__upsert_many.py` — `_upsert_many_sql` loops `for table in normalized`
- `src/finsight/adapters/vector_store/_aurora_pg_vector_write_upsert_chunks.py` — `for chunk in chunks: await _upsert_one(...)` (one write per chunk, after a single `_existing` batch fetch)
- Memory stores mirror the same loop (`_upsert_memory`, `_upsert_many_memory`).

These are the "eliminate N+1 transaction fan-out" targets: each ingestion of N chunks/metrics/tables issues N sequential statements (and N transaction touches) instead of one batched upsert.

### 3. Rerank batches are sequential, not parallel
- `src/finsight/adapters/rerank/_rerank_operations.py` `_score()` loops `for start in range(0, len(candidates), self.batch_size)` and `await _score_batch(...)` one batch at a time.
- Config has `rerank_parallel_batches: 2` (§5.24) and the adapter exposes `batch_size`, but there is no use of `rerank_parallel_batches` and no `asyncio.gather` across batches.

### 4. Embedding batches are sequential
- `src/finsight/adapters/embedding/_embedding_embed.py` loops `for start in range(0, len(texts), self.batch_size): vectors = await _embed_batch(...)` sequentially. For large uploads this serializes N embedding calls. No parallel batch option.

### 5. No request-level dedup / single-flight on the backend
- Answer cache exists, but there is no in-flight request coalescing: two identical concurrent questions both run the full flow. Only SQS has `MessageDeduplicationId`. No single-flight cache in `adapters/cache`.

### 6. Frontend has no TanStack Query (or equivalent)
- `web/package.json` has no `@tanstack/react-query`, `swr`, or `react-query`. All data fetching is manual `useEffect` + `useState` + `fetch` in client components:
  - `web/src/app/(app)/ask/ask-screen.tsx` (documents count, threads)
  - `web/src/app/(app)/documents/documents-library.tsx` (list + detail)
  - `web/src/app/(app)/upload/upload-form.tsx`
  - `web/src/components/ui/source-viewer.tsx`
- Consequences: no stale-while-revalidate, no background refetch, no automatic request dedup, no cache sharing between components, no retry/backoff, and each mount re-fetches.

### 7. No client-side request dedup / parallel loading
- `grep` for `Promise.all` / `Promise.allSettled` in `web/src` returns 0. Independent calls (documents list + threads on the ask page) are fired from separate `useEffect`s and not coordinated.
- No `React.cache`/`unstable_cache` for data queries; only `getServerSession` is cached.

### 8. No server-side data prefetch
- Pages (`ask/page.tsx`, `documents/page.tsx`, `upload/page.tsx`) are server components that only do auth (`requireCurrentUser`) and then render client components. No server-side fetch of documents/threads, so the client must waterfall after hydration. Next.js request dedup therefore never applies to data.

### 9. Source viewer / ingestion steps are sequential pipelines
- `source_viewer` steps (`resolve_version`, `fetch_content`, etc.) and ingestion steps (`read`, `chunk`, `embed`, `save`, `delta`, `cascade`) execute one after another with no `asyncio.gather` even where independent (e.g., metrics recompute vs. chunk save). Harder to prove without reading each, but no gather anywhere in `src/finsight/application`.

## What is NOT a gap (already aligned)

- Config switches and validation for `parallel_steps`, `rerank_parallel_batches`, `db_connections_per_request`, `db_pool_size_per_function` exist and are enforced (`src/finsight/core/config/models/config.py`).
- LLM gateway implements true parallel primary/backup with cancellation.
- Answer cache key includes company/role/scope/question/stamp (per §5.15).
- Ingestion already does page-level dedup and chunk-id-based delta tracking.

## Recommended remediation (one unit per item, each gated by `make preflight`)

1. **Batch the repository upserts** (chunks, metrics, document tables, vector writes) into single multi-row statements (or `executemany`), keeping the same return shape. Biggest concrete win for ingestion latency and DB connection usage. Add contract tests asserting batched calls.
2. **Implement `parallel_steps` in `AskQuestion._heavy`** using `asyncio.gather` for independent steps (embed + metrics list + understand; search + calculate), guarded by the switch, with the sequential path retained and tested (§5.11 "both paths written and tested").
3. **Parallelize rerank batches** using `asyncio.gather` over `rerank_parallel_batches` groups; honor the config value.
4. **Parallelize embedding batches** (opt-in, bounded by provider limits).
5. **Add TanStack Query** to `web` for documents, threads, source viewer; convert the `useEffect` fetches to `useQuery`/`useMutation`, enabling dedup, caching, background refetch, and optimistic updates.
6. **Server-prefetch** initial documents/threads in the page server components and pass as `initialData` to the queries (eliminates the client waterfall).
7. **Add request single-flight** for identical in-flight questions on the backend.
8. **Ratchet architecture/perf gates** to assert no per-entity DB calls in hot paths (extend `tests/architecture` and `tests/perf`).

## Open questions

- Scope as one hardening spec issue (like #115) or separate per-technique issues?
- Frontend migration target TanStack Query v5 (compatible with React 19.3.1 / Next 16.4.3 in `web/package.json`)?
- For the N+1 batch work, is preserving per-row RETURNING semantics (IDs/versions) required, or can we return input entities on conflict?
