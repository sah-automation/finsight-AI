# Placeholder for the golden set suite.
# The 100+ question set will live here, run against pilot and standard config.
# Remove this file when the first golden question exists.

from __future__ import annotations

import pytest


@pytest.mark.skip(reason='No golden question set yet')
def test_golden_suite_pending() -> None:
    """Keeps the golden suite selectable while the codebase is empty."""
