# finsight package

Root package for FinSight AI following clean architecture layers.

## Layer map
- `core/` - Shared basics, no business rules. Only place that reads config/env.
- `domain/` - Pure business logic, no vendor imports. Entities, value objects, services, ports.
- `application/` - Use cases orchestrating domain + ports. No direct vendor/adapter imports.
- `adapters/` - Vendor implementations implementing ports (LLM, storage, DB, etc.).
- `entrypoints/` - Thin doors (API, workers, scheduled) with no business logic.
- `composition/` - Composition root wiring everything together.

## Rules
- Follow dependency direction enforced by import-linter (see `pyproject.toml`)
- Every query must carry `company_id` (tenant isolation)
- No hard-coded values - use config
- Business logic never knows about vendors

## Dependency direction

```
entrypoints -> application -> domain <- adapters
                  ^                        |
                  +---- composition -------+
```

`domain` never imports outer layers or vendor libraries. `adapters` never
import each other. Only `composition` selects concrete adapters.
