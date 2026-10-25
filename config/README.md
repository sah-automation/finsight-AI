# Configuration Files

Schema and environment-specific config files.

**Files:**
- `schema.yaml` - config schema (source of truth)
- `permissions.yaml` - role/action/category matrix
- `prices.yaml` - model/service pricing
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
