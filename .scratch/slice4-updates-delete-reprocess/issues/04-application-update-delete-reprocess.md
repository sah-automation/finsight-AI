# 04: Application use cases - Update, Delete, Reprocess

**What to build:** Implement application use cases for updates, soft delete/restore/purge, and rolling reprocess. Update flow validates upload form (category/period/status/upload_type/replaces_document_id), does duplicate check, creates new DocumentVersion, enqueues pipeline with delta tracking. Delete does soft delete, clears cache, schedules purge after retention keeping audit. Reprocess is rolling/lower priority, idempotent, never mixes old/new, stays on current done version until new commits atomically.

**Blocked by:** 01: Domain foundations - DeltaDiffer, DocumentStamp, Chunk entity and ports, 02: Adapters - Chunk repository, vector/cache/messaging support, 03: Ingestion pipeline - Delta integration, atomic supersession, cascade

**Status:** ready-for-agent

- [ ] Create `src/finsight/application/update_document/` (update_document use case) - validate form, duplicate check, create new DocumentVersion, enqueue with delta tracking
- [ ] Create `src/finsight/application/delete_document/` (delete_document use case) - soft delete, clear answer cache, schedule/purge after `deleted_retention_days`, keep audit entry, idempotent
- [ ] Create `src/finsight/application/reprocess/` (reprocess use case) - rolling reprocess few companies at a time, lower priority, idempotent, never mix chunks/vectors, atomic commit superseding old
- [ ] Ensure on update: recompute affected metrics by code (log/flag), change stamp clears cache, flag other docs same company/period as "may be affected", log/audit dependent/stale items per Phase 1 rules
- [ ] Tests for soft delete/restore/purge with retention pass
- [ ] Tests for reprocess (rolling, no mixing, idempotent) pass
- [ ] Tests for stamp change clearing cache pass
- [ ] Tests for cascade/flagging other docs same company/period pass
