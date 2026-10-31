"""Alias module for the current-user endpoint.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from finsight.entrypoints.api import current_user as _cu
from finsight.entrypoints.api.current_user import *  # noqa: F403

router = _cu.router
EXTRA_ROUTERS = _cu.EXTRA_ROUTERS
_handle = _cu._handle
current_user = _cu.current_user
me = _cu.me
__all__ = list(getattr(_cu, '__all__', []))
