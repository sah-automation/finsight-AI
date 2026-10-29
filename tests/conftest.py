# Shared pytest configuration.
# Automatically applies the suite marker based on the test directory so that
# `pytest tests/unit -m unit` and the CI selectors always work.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MARKER_BY_DIR = {
    'unit': pytest.mark.unit,
    'integration': pytest.mark.integration,
    'golden': pytest.mark.golden,
    'contract': pytest.mark.contract,
    'architecture': pytest.mark.architecture,
    'security': pytest.mark.security,
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


# ============================================================
# Placeholder guard (issue #74)
# ============================================================
# pytest returns exit code 0 when every collected test is skipped. That makes a
# suite whose tests are all placeholders look green. Count the tests that
# actually execute (pass, fail, or error) and fail the session when that number
# is zero, so placeholder-only suites cannot masquerade as coverage.
_NON_SKIPPED_TESTS = 0


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Count tests that were not skipped."""
    global _NON_SKIPPED_TESTS  # noqa: PLW0603
    if report.when != 'call':
        return
    if getattr(report, 'skipped', False):
        return
    _NON_SKIPPED_TESTS += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail a session that collected tests but executed none of them."""
    global _NON_SKIPPED_TESTS  # noqa: PLW0603
    del exitstatus  # ``session.exitstatus`` is the authoritative value.
    collect_only = False
    try:
        collect_only = bool(session.config.getoption('collectonly', False))
    except ValueError:
        collect_only = False
    if collect_only:
        return
    collected = getattr(session, 'items', [])
    if not collected:
        # An empty selection already exits non-zero from pytest itself.
        _NON_SKIPPED_TESTS = 0
        return
    if _NON_SKIPPED_TESTS == 0:
        print(
            '\n\u274c Suite has no non-skipped tests (placeholder-only); '
            'see tests/README.md for tracked placeholders.',
            file=sys.stderr,
        )
        session.exitstatus = 1
    _NON_SKIPPED_TESTS = 0
