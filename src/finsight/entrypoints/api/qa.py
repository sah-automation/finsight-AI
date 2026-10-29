"""Alias API entrypoint for Q&A (re-exports ask module)."""

from .ask import *  # noqa: F403
from .ask import router_qa as router  # noqa: F401

# Ensure route prefix matches module for convenience routers.
