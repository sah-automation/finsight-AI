# Domain Ports

Interfaces (abstract classes or Protocols) that the outside world must fulfil.

**Belongs here:**
- `LLMGateway` - generate, stream, embed
- `VectorSearch` - semantic search
- `VectorWrite` - upsert vectors
- `DocumentReader` - extract text/tables from files
- `DocumentRepository` - CRUD for documents
- `ChunkRepository` - CRUD for chunks
- `MetricRepository` - CRUD for metrics
- `CachePort` - get/set with TTL
- `QueuePort` - enqueue jobs
- `AuthPort` - verify token, get role
- `MeteringPort` - record usage

**Naming convention:** Ports end with what they are (`Gateway`, `Search`, `Repository`, `Reader`).

**Does not belong here:**
- Implementations (those go in `adapters/`)
- Base classes with shared code (unless truly shared by all implementations)
- Config-specific logic
