"""Tests for the load and performance harness itself."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import performance_harness

pytestmark = [pytest.mark.performance, pytest.mark.load, pytest.mark.perf, pytest.mark.benchmark]


def test_budgets_cover_required_categories() -> None:
    budgets = performance_harness.BUDGETS
    for key in (
        'first_word_timing',
        'streaming_behavior',
        'search',
        'reranking',
        'database_interactions',
    ):
        assert key in budgets
    assert 'first_word_timing' in performance_harness.PERFORMANCE_BUDGETS


def test_profile_environment_and_concurrency() -> None:
    assert performance_harness.profile_to_environment('pilot') == 'development'
    assert performance_harness.profile_to_environment('standard') == 'staging'
    assert (
        performance_harness.concurrency_cap_for('pilot')
        == performance_harness.PILOT_CONCURRENCY_CAP
    )


def test_waiting_line_limits_concurrency() -> None:
    async def run() -> None:
        waiting_line = performance_harness.WaitingLineHarness(2)
        started: list[float] = []

        async def work() -> int:
            started.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.01)
            return 1

        results = await asyncio.gather(*[waiting_line.run('company-1', work) for _ in range(5)])
        assert all(result == 1 for result in results)
        assert waiting_line.waited_count > 0
        assert waiting_line.max_queue_depth >= 2

    asyncio.run(run())


def test_qa_load_returns_metrics() -> None:
    report = asyncio.run(
        performance_harness.run_load(
            profile='pilot', scenario='qa', requests=12, concurrency=4, seed=7
        )
    )
    assert report['requests'] == 12
    assert report['throughput_qps'] > 0
    assert 'first_word_ms' in report
    assert 'p95' in report['first_word_ms']
    assert 'waiting_line' in report
    assert report['budgets_met'] is True


def test_ingestion_load_returns_metrics() -> None:
    report = asyncio.run(
        performance_harness.run_load(profile='pilot', scenario='ingestion', requests=6, seed=7)
    )
    assert report['scenario'] == 'ingestion'
    assert report['requests'] == 6
    assert 'p95' in report['first_word_ms']
    assert report['budgets_met'] is True


def test_load_baseline_round_trip(tmp_path: Path) -> None:
    report = asyncio.run(
        performance_harness.run_load(
            profile='pilot', scenario='qa', requests=4, concurrency=2, seed=1
        )
    )
    performance_harness.write_baseline(report, tmp_path / 'baseline.json')
    loaded = performance_harness.load_baseline(path=tmp_path / 'baseline.json')
    assert loaded['profile'] == 'pilot'
