"""Dependency-gate tests for modules required by the configured model providers.

CI must fail fast when the Python environment lacks modules required by model
provider paths (e.g. LiteLLM's Gemini embedding path importing ``google.auth``),
so dependency drift can never silently kill retrieval again.
"""

from __future__ import annotations

import importlib.util


def _module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def test_google_auth_is_importable_for_gemini_embedding_path() -> None:
    """The exact import LiteLLM's Gemini embedding path performs must succeed."""
    assert _module_exists('google.auth')
