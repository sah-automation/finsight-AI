"""Meta-tests for the golden scoring harness (issue #77)."""

from __future__ import annotations

from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent.parent / 'golden'


@pytest.mark.architecture
class TestGoldenScoringCoverage:
    def test_pending_placeholder_removed(self) -> None:
        assert not (GOLDEN / 'test_golden_pending.py').exists()

    def test_runner_and_scorer_exist(self) -> None:
        assert (GOLDEN / 'run_golden.py').exists()
        assert (GOLDEN / 'compare_results.py').exists()

    def test_baseline_exists(self) -> None:
        assert (GOLDEN / 'baseline.json').exists() or (GOLDEN / 'baselines').exists()

    def test_suite_has_non_placeholder_test(self) -> None:
        tests = list(GOLDEN.glob('test_*.py'))
        assert tests, 'golden suite must contain at least one non-placeholder test'
