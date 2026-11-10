"""Dependency-gate tests for modules required by the configured model providers.

CI must fail fast when the Python environment lacks modules required by model
provider paths (e.g. LiteLLM's Gemini embedding path importing ``google.auth``),
so dependency drift can never silently kill retrieval again.
"""

from __future__ import annotations

import importlib


def test_google_auth_is_importable_for_gemini_embedding_path() -> None:
    """The exact import LiteLLM's Gemini embedding path performs must succeed."""
    assert importlib.import_module('google.auth') is not None
