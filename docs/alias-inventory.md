# Alias Inventory

Reviewed compatibility shim modules and canonical module choices.

| Alias module | Canonical module(s) | Reason / status |
|---|---|---|
| `finsight/adapters/readers/router.py` | `finsight.adapters.readers.page_router` | Canonical router hub (retained public surface); no retained backward-compatible alias (removed unused PageRouterAlias). Owner: composition maintainers; removal condition: none unless routing importers are repointed. |
| `finsight/entrypoints/api/main.py` | `finsight.entrypoints.api.app` | Deployment/public surface (ASGI entrypoint); re-exports `create_app` and lazily exposes `app` via module `__getattr__` so importing it has no wiring side effects. Owner: platform; removal condition: none (CDK references this module). |

## Final pass-through count

Final pass-through module count: **2** (`adapters/readers/router.py`, `entrypoints/api/main.py`).
