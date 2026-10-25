# finsight

Package root for the FinSight AI backend.

## Layer map

| Package | Responsibility |
| --- | --- |
| `core/` | Shared basics: config loading, errors, logging, ids/enums, value objects |
| `domain/` | Pure business logic: entities, value objects, services, ports |
| `application/` | Use cases that orchestrate domain rules and ports |
| `adapters/` | Vendor implementations of ports (LLM, storage, repositories, ...) |
| `entrypoints/` | Thin API, worker, and scheduled entry doors |
| `composition/` | The composition root that wires concrete implementations |

## Dependency direction

```
entrypoints -> application -> domain <- adapters
                  ^                        |
                  +---- composition -------+
```

`domain` never imports outer layers or vendor libraries. `adapters` never
import each other. Only `composition` selects concrete adapters. The rules are
enforced by `lint-imports` and `tests/architecture/`.
