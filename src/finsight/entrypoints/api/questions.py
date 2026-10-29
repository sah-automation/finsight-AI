"""Alias API entrypoint for Q&A (re-exports ask module)."""

from .ask import *  # noqa: F403
from .ask import router_questions as router  # noqa: F401
