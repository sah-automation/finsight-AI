# Domain

Pure business logic. No AWS, no HTTP, no vendor imports.

**Dependency rule:** Domain imports nothing from `application`, `adapters`, or `entrypoints`.

**Belongs here:**
- Entities (`entities/`)
- Value objects (`value_objects/`)
- Business rule services (`services/`)
- Ports (interfaces) (`ports/`)

**Does not belong here:**
- Any vendor SDK imports (boto3, litellm, etc.)
- Database queries (use repository ports)
- HTTP handling
- Config reading (use injected config objects)
