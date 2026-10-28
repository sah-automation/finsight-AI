# 02: Adapters - Chunk repository, vector/cache/messaging support

**What to build:** Implement adapters for the new ports so the system can persist chunks with stable ids, mark inactive chunks, support writing only changed chunks during reprocess without mixing old/new, clear answer cache on update/delete, and publish change events. Wire through composition root.

**Blocked by:** 01: Domain foundations - DeltaDiffer, DocumentStamp, Chunk entity and ports

**Status:** ready-for-agent

- [ ] Implement `src/finsight/adapters/repositories/postgres_chunk_repository.py` with stable chunk id upsert, marking inactive, partition-aware queries (company_id enforced)
- [ ] Extend `src/finsight/adapters/repositories/postgres_document_repository.py` to support version supersession, soft delete, recycle bin listing, audit-friendly queries
- [ ] Ensure `src/finsight/adapters/cache/answer_cache.py` clears on upload/update/delete and key includes document stamp (verify against `domain/services/cache_key`)
- [ ] Add `src/finsight/adapters/messaging/change_event_publisher.py` (or extend queue adapter) to publish change events/cascade signals
- [ ] Update vector store adapters to support writing only changed chunks and not mixing old/new during reprocess
- [ ] Wire new adapters in composition root; respect DI only
- [ ] Contract tests for new ports pass
