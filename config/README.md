# Configuration Files

Schema and environment-specific config files.

**Files:**
- `schema.yaml` - config schema (source of truth)
- `permissions.yaml` - role/action/category matrix (**planned** for runtime; read by the security tests; issue #11)
- `prices.yaml` - model/service pricing (**planned**, not read by code yet; issue #11)
- `dev.yaml`, `test.yaml`, `staging.yaml`, `prod.yaml` - environment values

**Rules:**
- Only `core/config` reads these files
- Config is typed, frozen, validated at startup
- Missing/unknown values stop the app (no silent fallback)
- Invalid combinations rejected by config module
- Log all active switches at startup

**Does not belong here:**
- Code
- Secrets (use secret store, referenced in env files)
