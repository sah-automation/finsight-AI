# Placeholder for the integration test suite.
# Real adapters and real local services will be exercised here.
# Remove this file when the first integration test exists.

from __future__ import annotations

import pytest


@pytest.mark.skip(reason='No adapters implemented yet')
def test_integration_suite_pending() -> None:
    """Keeps the integration suite selectable while the codebase is empty."""
