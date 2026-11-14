"""Compatibility alias for the ingest upload application package."""

from finsight.application.ingest_document import *  # noqa: F401,F403
from finsight.application.ingest_document import __all__ as _all  # noqa: F401

__all__ = list(_all)
