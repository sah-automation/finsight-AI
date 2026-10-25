# Application

Use cases that orchestrate domain logic and ports. No vendor imports.

**Dependency rule:** Application imports `domain` only. Never imports `adapters`.

**Belongs here:**
- One folder per use case (question flow, ingestion, metrics, etc.)
- Each use case is a class taking ports in its constructor
- Flow steps as small, single-purpose classes

**Does not belong here:**
- Vendor SDK calls
- Database queries (use repository ports)
- Config reading (inject config objects)
- HTTP handling (that's `entrypoints/`)
