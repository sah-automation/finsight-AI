"""Pytest guard against false-green placeholder test suites.

A suite that contains only skipped tests exits 0 under pytest, which lets
placeholder-heavy suites look green. Track, per collected test item, whether any
report was skipped; a session with no unskipped item fails. Issue #74.
"""

from __future__ import annotations

import sys

import pytest  # noqa: TC002

# nodeid -> True when the item was ultimately skipped.
_PLACEHOLDER_STATE: dict[str, bool] = {}


def _reset() -> None:
    _PLACEHOLDER_STATE.clear()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record the skip state of every collected test item."""
    nodeid = report.nodeid
    # A test is skipped when *any* of its reports (setup/call/teardown) is
    # skipped. Track False first so a subsequent skipped report wins, and an
    # erroring setup (outcome ``error``, skipped=False) stays non-skipped.
    if nodeid not in _PLACEHOLDER_STATE:
        _PLACEHOLDER_STATE[nodeid] = False
    if getattr(report, 'skipped', False):
        _PLACEHOLDER_STATE[nodeid] = True


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail a session that collected tests but executed none of them."""
    del exitstatus  # ``session.exitstatus`` is authoritative.
    collect_only = False
    try:
        collect_only = bool(session.config.getoption('collectonly', False))
    except ValueError:
        collect_only = False
    if collect_only:
        _reset()
        return
    collected = getattr(session, 'items', [])
    if not collected:
        _reset()
        return
    executed = sum(1 for skipped in _PLACEHOLDER_STATE.values() if not skipped)
    if executed == 0:
        print(
            '\n\u274c Suite has no non-skipped tests (placeholder-only); '
            'see tests/README.md for tracked placeholders.',
            file=sys.stderr,
        )
        session.exitstatus = 1
    _reset()
