# Shared pytest configuration.
# Automatically applies the suite marker based on the test directory so that
# `pytest tests/unit -m unit` and the CI selectors always work.

from __future__ import annotations

from pathlib import Path

import pytest

_MARKER_BY_DIR = {
    'unit': pytest.mark.unit,
    'integration': pytest.mark.integration,
    'golden': pytest.mark.golden,
    'contract': pytest.mark.contract,
    'architecture': pytest.mark.architecture,
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Add the suite marker implied by the test's directory."""
    del config  # Unused, required by the hook signature.
    for item in items:
        parts = Path(str(item.fspath)).parts
        if 'tests' not in parts:
            continue
        index = parts.index('tests')
        if index + 1 >= len(parts):
            continue
        marker = _MARKER_BY_DIR.get(parts[index + 1])
        if marker is not None:
            item.add_marker(marker)
