"""Meta-tests for the load and performance baseline harness (issue #79)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CANDIDATE_DIRS = [
    ROOT / 'performance',
    ROOT / 'load',
    ROOT / 'perf',
    ROOT / 'loadtest',
    ROOT / 'loadtests',
]


def _dirs() -> list[Path]:
    return [path for path in CANDIDATE_DIRS if path.exists()]


@pytest.mark.architecture
class TestLoadPerformanceBaselineCoverage:
    def test_suite_directory_exists(self) -> None:
        assert _dirs(), 'expected at least one performance/load test directory'

    def test_harness_exists(self) -> None:
        assert any(
            (base / 'performance_harness.py').exists()
            or (base / 'load_harness.py').exists()
            or (base / 'harness.py').exists()
            for base in _dirs()
        ), 'load harness not found'

    def test_runner_exists(self) -> None:
        assert any(
            (base / 'run_load.py').exists() or (base / 'run_performance.py').exists()
            for base in _dirs()
        ), 'load runner not found'

    def test_baseline_exists(self) -> None:
        assert any(
            (base / 'baselines').exists() or any(base.glob('baseline*.json')) for base in _dirs()
        ), 'performance baseline not found'

    def test_no_pending_placeholder(self) -> None:
        for base in _dirs():
            assert not (base / 'test_load_pending.py').exists()
            assert not (base / 'test_performance_pending.py').exists()
            assert not (base / 'test_perf_pending.py').exists()

    def test_suite_has_non_placeholder_test(self) -> None:
        for base in _dirs():
            tests = list(base.glob('test_*.py'))
            assert tests, f'performance suite must contain tests: {base}'
