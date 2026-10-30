"""Alias module for the current-user endpoint."""

from finsight.entrypoints.api import current_user as _cu
from finsight.entrypoints.api.current_user import *  # noqa: F403

router = _cu.router
EXTRA_ROUTERS = _cu.EXTRA_ROUTERS
__all__ = list(getattr(_cu, '__all__', []))
