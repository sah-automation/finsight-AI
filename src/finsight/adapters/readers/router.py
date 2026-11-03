"""Canonical router hub for page routing (deployment/public surface).

This module is the stable public spelling for ``PageRouter``; it re-exports the
implementation from :mod:`finsight.adapters.readers.page_router`. ``PageRouterAlias``
is retained for backwards compatibility (owner: composition; remove once all
callers use ``page_router`` directly).
"""

from .page_router import PageRouter

__all__ = ['PageRouter']
# Backwards-friendly aliases.
PageRouterAlias = PageRouter
