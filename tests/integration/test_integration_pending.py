# Placeholder for the integration test suite.
# Tracked placeholder (issue #74/#75): remove this file when the first
# integration test lands.

from __future__ import annotations

import pytest


@pytest.mark.placeholder
@pytest.mark.skip(reason='Placeholder pending first adapter integration test (#74)')
def test_integration_suite_pending() -> None:
    """Keeps the integration suite selectable while the codebase is empty."""
