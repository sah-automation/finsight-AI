# 05: Entrypoints, migrations, hardening

**What to build:** Expose document lifecycle via API (document library, recycle bin, soft delete/restore/purge), update upload API validation per requirements, ensure workers wired correctly, extend migrations for hashes/stable ids/active flags/stamps/soft delete/supersession, and verify all switch paths and tests.

**Blocked by:** 01: Domain foundations - DeltaDiffer, DocumentStamp, Chunk entity and ports, 02: Adapters - Chunk repository, vector/cache/messaging support, 03: Ingestion pipeline - Delta integration, atomic supersession, cascade, 04: Application use cases - Update, Delete, Reprocess

**Status:** ready-for-agent

- [ ] Create/update `src/finsight/entrypoints/api/documents.py` - list/search, get metadata, soft delete, restore (within retention), permanent purge (privileged/audited), recycle bin; enforce company/role/access scope
- [ ] Update `src/finsight/entrypoints/api/upload.py` - require category/period/status/upload_type/replaces_document_id for updates, duplicate check suggests update, reject if partition missing, virus scan before enqueue, upload_type delete no longer handled here
- [ ] Update/ensure `src/finsight/entrypoints/workers/*` wired for delta/cascade; reprocess jobs routed with lower priority
- [ ] Extend migrations for page hashes, chunk hashes/stable ids, chunk active/inactive flags, document stamps, soft delete fields/timestamps, version supersession tracking, audit fields; must work across partitions
- [ ] Verify all switch paths tested ON/OFF, import-linter passes, config validation passes, golden set not broken
- [ ] All Slice 4 tests pass (delta, supersession, delete/restore/purge, reprocess, stamp/cache, cascade)
