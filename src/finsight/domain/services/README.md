# Domain Services

Pure business rules that don't belong on a single entity.

**Belongs here:**
- Evidence checking rules (`evidence.py`)
- Tenant-scoped cache key composition (`cache_key.py`)
- Role/category permission checks (`permission_policy.py`)
- Conflict detection between sources
- Chunking strategies
- Output validation rules

**Does not belong here:**
- Any I/O (database, HTTP, file system)
- Vendor SDK calls
- Orchestration of multiple steps (that's `application/`)
- Config reading (inject config objects)
