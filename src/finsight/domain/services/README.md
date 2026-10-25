# Domain Services

Pure business rules that don't belong on a single entity.

**Belongs here:**
- Evidence checking rules
- Conflict detection between sources
- Chunking strategies
- Output validation rules
- Role/category permission checks (reading from injected config)

**Does not belong here:**
- Any I/O (database, HTTP, file system)
- Vendor SDK calls
- Orchestration of multiple steps (that's `application/`)
- Config reading (inject config objects)
