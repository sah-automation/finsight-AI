# Alias Inventory

Reviewed compatibility shim modules and canonical module choices.

| Alias module | Canonical module(s) | Reason / status |
|---|---|---|
| `finsight/adapters/readers/router.py` | `finsight.adapters.readers.page_router` | Canonical router hub (retained public surface); PageRouterAlias retained for backwards compatibility; owner: composition maintainers; removal condition: none unless routing importers are repointed. |
| `finsight/entrypoints/api/main.py` | `finsight.entrypoints.api.app` | Deployment/public surface (ASGI entrypoint alias); owner: platform; removal condition: none (CDK references `finsight.entrypoints.api.main`). |

## Final pass-through count

Final pass-through module count: **2** (`adapters/readers/router.py`, `entrypoints/api/main.py`).
