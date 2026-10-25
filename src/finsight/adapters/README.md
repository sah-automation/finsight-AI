# Adapters

The ONLY place vendor code lives. Each adapter implements a domain port.

**Dependency rule:** Adapters import `domain` (to implement ports). Adapters never import each other.

**Belongs here:**
- One folder per vendor integration
- Each adapter implements exactly one port
- Decorators for retry, caching, metering, tracing

**Does not belong here:**
- Business logic (that's `domain/services/` or `application/`)
- Cross-adapter calls (go through application layer)
- Config reading (inject config objects)