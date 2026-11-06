"""Regression test for ingestion worker poll loop resilience (issue #238)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))

import run_ingestion_worker as worker  # type: ignore[import-not-found]

pytestmark = pytest.mark.unit


class _StubQueue:
    def __init__(self) -> None:
        self.calls = 0

    async def receive(self, **kwargs: object) -> list[dict]:
        self.calls += 1
        if self.calls == 1:
            raise TypeError('boom')
        return []

    async def ack(self, message: object) -> None:
        return None

    async def nack(self, message: object) -> None:
        return None


class _StubPipeline:
    async def run_pipeline(self, context: object) -> dict:
        return {'status': 'completed'}


async def test_typeerror_on_first_receive_is_absorbed(caplog: pytest.LogCaptureFixture) -> None:
    queue = _StubQueue()
    pipeline = _StubPipeline()

    with caplog.at_level(logging.ERROR, logger='finsight.ingestion_worker'):
        await worker.run_worker(
            queue=queue,
            pipeline=pipeline,
            max_iterations=2,
            poll_interval=0,
            wait_time_seconds=1,
        )

    assert queue.calls == 2
    assert any('Receive failed' in record.getMessage() for record in caplog.records)
