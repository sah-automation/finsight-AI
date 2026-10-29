# Placeholder for the golden set suite.
# Tracked placeholder (issue #77): remove this file when the first golden
# question lands.

from __future__ import annotations

import pytest


@pytest.mark.placeholder
@pytest.mark.skip(reason='Placeholder pending golden scoring harness (#77)')
def test_golden_suite_pending() -> None:
    """Keeps the golden suite selectable while the codebase is empty."""
