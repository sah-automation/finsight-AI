# Placeholder for the contract test suite.
# Tracked placeholder (issue #75): remove this file when the first shared port
# contract test lands.

from __future__ import annotations

import pytest


@pytest.mark.placeholder
@pytest.mark.skip(reason='Placeholder pending port contract matrix (#75)')
def test_contract_suite_pending() -> None:
    """Keeps the contract suite selectable while the codebase is empty."""
