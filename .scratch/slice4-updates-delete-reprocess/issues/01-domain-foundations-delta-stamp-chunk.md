# 01: Domain foundations - DeltaDiffer, DocumentStamp, Chunk entity and ports

**What to build:** Add pure domain foundations for delta tracking and version lifecycle. Create `DeltaDiffer` and `DocumentStamp` as pure domain services (no I/O), add a `Chunk` domain entity/value object with stable chunk ids and hashes, and add ports for chunk repository and change event publishing. This enables all other slices without layer violations.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Create `src/finsight/domain/services/delta_differ.py` with pure diffing logic for pages and chunks (deterministic, returns added/changed/removed/unchanged)
- [ ] Create `src/finsight/domain/services/document_stamp.py` with pure logic to compute/update document stamp (hash of relevant version state)
- [ ] Add `src/finsight/domain/entities/chunk.py` (or equivalent) for chunks with stable chunk ids, parent/child, hashes, company/document/version - pure domain
- [ ] Add `src/finsight/domain/ports/chunk_repository.py` with methods for chunk CRUD (upsert by stable chunk id, mark inactive, list by version/document) requiring company_id
- [ ] Add/extend `src/finsight/domain/ports/change_event_publisher.py` (or existing port) for publishing change events/cascade signals
- [ ] Export from `__init__` files as needed; follow Clean Architecture (domain has no external imports)
- [ ] Unit tests for `DeltaDiffer` and `DocumentStamp` cover edge cases (empty, no changes, additions/removals)
