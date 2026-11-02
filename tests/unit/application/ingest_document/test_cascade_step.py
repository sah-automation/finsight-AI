from __future__ import annotations

import asyncio
from types import SimpleNamespace

from finsight.application.ingest_document.cascade_step import CascadeStep


class _DocRepo:
    async def list_documents(self, company_id) -> list[object]:
        return [
            SimpleNamespace(id='doc1', period='Q1'),
            SimpleNamespace(id='doc2', period='Q1'),
            SimpleNamespace(id='doc3', period='Q2'),
        ]


class _MetricRepo:
    def __init__(self) -> None:
        self.calls = []

    async def mark_stale(self, company_id, document_ids) -> None:
        self.calls.append((company_id, list(document_ids)))


class _Cache:
    def __init__(self) -> None:
        self.calls = []

    async def clear_company(self, company_id) -> None:
        self.calls.append(company_id)


class _Publisher:
    def __init__(self) -> None:
        self.events = []

    async def request_cascade(
        self, company_id, document_id=None, version_id=None, category=None, period=None, job_id=None
    ) -> None:
        self.events.append(('request', company_id, document_id))

    async def publish_many(self, company_id, events) -> None:
        self.events.append(('many', company_id, list(events)))


def test_cascade_step_flags_affected_docs_and_publishes_cascade() -> None:
    metric_repo = _MetricRepo()
    publisher = _Publisher()
    cache = _Cache()
    step = CascadeStep(
        document_repository=_DocRepo(),
        metric_repository=metric_repo,
        change_event_publisher=publisher,
        answer_cache=cache,
        config=None,
    )
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        category='cat',
        period='Q1',
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.affected_documents == ['doc2']
    assert ctx.affected_count == 1
    assert ctx.status == 'cascaded'
    assert metric_repo.calls == [('co', ['doc2'])]
    assert any(kind == 'request' for kind, *_ in publisher.events)
    assert any(kind == 'many' for kind, *_ in publisher.events)
    assert cache.calls == ['co', 'co']
