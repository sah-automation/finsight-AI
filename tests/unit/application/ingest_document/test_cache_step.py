from __future__ import annotations

import asyncio
from types import SimpleNamespace

from finsight.application.ingest_document.cache_step import CacheStep


class _Cache:
    def __init__(self) -> None:
        self.calls = []

    async def clear_company(self, company_id) -> None:
        self.calls.append(company_id)


def test_cache_step_clears_cache_and_reports_status() -> None:
    cache = _Cache()
    step = CacheStep(answer_cache=cache, config=None)
    ctx = SimpleNamespace(company_id='co', version_id='v1')

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.status == 'cache_cleared'
    assert ctx.cache_cleared is True
    assert cache.calls == ['co']
