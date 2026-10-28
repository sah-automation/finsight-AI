# 03: Ingestion pipeline - Delta integration, atomic supersession, cascade

**What to build:** Wire delta tracking through the ingestion pipeline workers so updates create new DocumentVersions, compute diffs using domain services, only embed changed/new chunks (mark removed inactive), perform atomic commit that supersedes previous version in the same transaction, updates document stamp, clears cache, and runs cascade/change event logic. Both delta ON and OFF paths must work.

**Blocked by:** 01: Domain foundations - DeltaDiffer, DocumentStamp, Chunk entity and ports, 02: Adapters - Chunk repository, vector/cache/messaging support

**Status:** ready-for-agent

- [ ] Integrate `DeltaDiffer`/`DocumentStamp` into delta worker and pipeline; compute page hashes, stable chunk ids, diff vs previous version
- [ ] Update pipeline workers to only embed changed/new chunks on delta path and mark removed chunks inactive; full reprocess when `delta_tracking` false
- [ ] Update save/commit logic to do atomic commit: save new version chunks/vectors/metrics, update document stamp, clear cache entries, mark previous version as SUPERSEDED, publish change event/cascade - all or nothing
- [ ] Update `src/finsight/application/ingest_document/cascade_worker.py` to flag other docs same company/period as "may be affected", publish events, mark dependent items stale (log/audit in Phase 1), never auto-edit other docs
- [ ] Ensure pipeline respects both paths and is idempotent (job id + upsert on stable chunk id)
- [ ] Switch tests for delta ON/OFF pass; tests for version supersession (new commit -> old superseded atomically) pass
