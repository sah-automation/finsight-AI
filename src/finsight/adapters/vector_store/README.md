# Vector Store Adapter

Vector search and storage using Aurora pgvector.

**Implements:** `VectorSearch` and `VectorWrite` ports (segregated)

**Belongs here:**
- `AuroraPgVectorSearch` - semantic search with filters
- `AuroraPgVectorWrite` - upsert/delete vectors
- Filter by company_id (mandatory)
- HNSW index management

**Does not belong here:**
- Chunking or embedding (separate adapters)
- Business logic about what to search
- Raw SQL for non-vector queries (that's repositories/)