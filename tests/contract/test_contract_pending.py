# Placeholder for the contract test suite.
# One shared test per port will live here, run against every adapter.
# Remove this file when the first port and its adapters exist.

from __future__ import annotations

import pytest


@pytest.mark.skip(reason='No ports implemented yet')
def test_contract_suite_pending() -> None:
    """Keeps the contract suite selectable while the codebase is empty."""
