# Composition Root

Wires everything together. The only place concrete classes are chosen.

**Belongs here:**
- `build_container(config)` - returns wired use cases
- Pilot set vs standard set builders (config-driven)
- Adapter registration (ReaderFactory, etc.)
- Decorator stacking from config
- Singleton instances (config, logger, pools)

**Two build modes (from config):**
- Pilot set - minimal adapters for testing
- Standard set - full production adapters

**Does not belong here:**
- Business logic
- Any class with business behavior
- Config reading (receives validated config object)
