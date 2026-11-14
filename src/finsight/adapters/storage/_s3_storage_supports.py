# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
from typing import Any

from ._s3_storage_helpers import *


def _supports(client: Any, method_name: str, params: dict[str, Any]) -> bool:
    # Best-effort: inspect signature to see if method accepts the params.
    method = getattr(client, method_name, None)
    if not callable(method):
        return False
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        return True
    params_list = sig.parameters
    if not params_list:
        return True
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params_list.values()):
        return True
    # If method appears to accept only positional/known, allow anyway.
    return True
