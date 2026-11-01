"""Contract tests for the WaitingLine port."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from finsight.adapters.waiting_line.passthrough_waiting_line import PassthroughWaitingLine
from finsight.adapters.waiting_line.waiting_line_adapter import WaitingLineAdapter
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports import WaitingLine

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


class WaitingLineContract:
    """Shared contract cases for any WaitingLine implementation."""

    @pytest.fixture
    def line(self) -> WaitingLine:
        raise NotImplementedError('Subclasses must implement the line fixture')

    async def test_runs_work_and_returns_its_result(self, line: WaitingLine) -> None:
        async def work() -> str:
            return 'answer'

        assert await line.run(COMPANY, work) == 'answer'

    async def test_runs_a_sync_work_callable(self, line: WaitingLine) -> None:
        assert await line.run(COMPANY, lambda: 'sync') == 'sync'

    async def test_work_failure_propagates_to_the_caller(self, line: WaitingLine) -> None:
        async def broken() -> None:
            raise RuntimeError('boom')

        with pytest.raises(RuntimeError, match='boom'):
            await line.run(COMPANY, broken)

    async def test_requires_company_id(self, line: WaitingLine) -> None:
        with pytest.raises((TypeError, ValueError)):
            await line.run(None, lambda: 'nope')  # type: ignore[arg-type]

    async def test_results_never_mix_tenant_data(self, line: WaitingLine) -> None:
        async def work(company: str) -> dict[str, str]:
            return {'company': company}

        results = await asyncio.gather(
            line.run(COMPANY, work, args=(str(COMPANY),)),
            line.run(OTHER_COMPANY, work, args=(str(OTHER_COMPANY),)),
        )
        assert [result['company'] for result in results] == [str(COMPANY), str(OTHER_COMPANY)]


class TestPassthroughWaitingLineContract(WaitingLineContract):
    @pytest.fixture
    def line(self) -> WaitingLine:
        return PassthroughWaitingLine()


class TestWaitingLineAdapterContract(WaitingLineContract):
    @pytest.fixture
    def line(self) -> WaitingLine:
        return WaitingLineAdapter(max_concurrency=1)
