# Core Config

The ONLY place that reads config files and environment variables.

**Belongs here:**
- Config schema definitions (Pydantic models)
- Config loading and validation logic
- Environment variable parsing

**Does not belong here:**
- Business logic
- Any code that uses config values (import from here instead)
- Hard-coded defaults (use the validated config object)