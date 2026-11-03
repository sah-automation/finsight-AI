"""Canonical router hub for page routing (deployment/public surface).

This module is the stable public spelling for ``PageRouter``; it re-exports the
implementation from :mod:`finsight.adapters.readers.page_router`. Retained as a
deployment/public surface because internal callers and docs refer to this path;
owner: composition maintainers; removal condition: none unless routing importers
are repointed.

The previously retained ``PageRouterAlias`` was not used anywhere and has been
removed.
"""

from .page_router import PageRouter

__all__ = ['PageRouter']
