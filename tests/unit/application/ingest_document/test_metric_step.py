from __future__ import annotations

import asyncio
from types import SimpleNamespace

from finsight.application.ingest_document.metric_step import MetricStep
from finsight.domain.value_objects.reader_result import ReaderResult


class _MetricRepo:
    def __init__(self) -> None:
        self.calls = []

    async def save_metrics(self, company_id, version_id, metrics=None) -> bool:
        self.calls.append((company_id, version_id, list(metrics or [])))
        return True


def test_metric_step_persists_metrics_from_context() -> None:
    repo = _MetricRepo()
    step = MetricStep(metric_repository=repo, config=None)
    ctx = SimpleNamespace(company_id='co', version_id='v1', metrics=[{'a': 1}])

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.status == 'metrics_persisted'
    assert ctx.persisted is True
    assert repo.calls == [('co', 'v1', [{'a': 1}])]


def test_metric_step_extracts_metrics_from_reader_result() -> None:
    repo = _MetricRepo()
    step = MetricStep(metric_repository=repo, config=None)
    rr = ReaderResult(text='Revenue 10', tables=[], page_numbers=[1])
    ctx = SimpleNamespace(company_id='co', version_id='v2', reader_result=rr)

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.status == 'metrics_persisted'
    assert len(ctx.metrics) >= 1
