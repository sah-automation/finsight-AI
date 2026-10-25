# Domain Entities

Core business objects with identity and lifecycle.

**Belongs here:**
- `Document` - source document with state machine
- `Chunk` - text/table chunk with embeddings
- `Metric` - calculated financial metric
- `Answer` - question answer with citations
- `Recommendation` - decision recommendation

**Does not belong here:**
- Value objects without identity (those go in `value_objects/`)
- DTOs for API responses (those go in `entrypoints/api/`)
- Database models (those go in `adapters/repositories/`)