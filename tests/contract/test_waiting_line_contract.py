"""Contract tests for the WaitingLine port."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from finsight.adapters.waiting_line.busy_result import BusyResult
from finsight.adapters.waiting_line.waiting_line_adapter import WaitingLineAdapter
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports import WaitingLine

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


async def _until(predicate: object, *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():  # type: ignore[operator]
            return
        await asyncio.sleep(0.001)
    raise AssertionError('condition was not reached')


class TestWaitingLineContract:
    async def test_runs_work_and_returns_its_result(self) -> None:
        line: WaitingLine = WaitingLineAdapter(max_concurrency=1)

        async def work() -> str:
            return 'answer'

        assert await line.run(COMPANY, work) == 'answer'

    async def test_enforces_the_concurrency_cap(self) -> None:
        line = WaitingLineAdapter(max_concurrency=2, max_per_company=2)
        active = 0
        peak = 0
        lock = asyncio.Lock()

        async def work() -> None:
            nonlocal active, peak
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.02)
            async with lock:
                active -= 1

        await asyncio.gather(*(line.run(COMPANY, work) for _ in range(6)))

        assert peak == 2

    async def test_timeout_returns_a_friendly_busy_result(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1, max_wait_seconds=0.05)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocker() -> str:
            started.set()
            await release.wait()
            return 'done'

        running = asyncio.create_task(line.run(COMPANY, blocker))
        await started.wait()

        result = await line.run(COMPANY, lambda: 'second')

        assert isinstance(result, BusyResult)
        assert result.busy is True
        assert result.company_id == str(COMPANY)
        assert 'busy' in result.message.lower()
        assert result.wait_seconds >= 0.05
        release.set()
        assert await running == 'done'

    async def test_quick_first_runs_quick_work_before_uploads(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1, max_per_company=2)
        order: list[str] = []
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocker() -> str:
            started.set()
            await release.wait()
            return 'blocker'

        running = asyncio.create_task(line.run(COMPANY, blocker))
        await started.wait()

        upload = asyncio.create_task(
            line.run(COMPANY, lambda: order.append('upload') or 'upload', priority='upload')
        )
        await _until(lambda: line.pending == 1)
        quick = asyncio.create_task(
            line.run(COMPANY, lambda: order.append('quick') or 'quick', priority='quick')
        )
        await _until(lambda: line.pending == 2)

        release.set()
        await asyncio.gather(running, upload, quick)

        assert order == ['quick', 'upload']

    async def test_first_come_keeps_arrival_order(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1, max_per_company=2, queue_priority='first_come')
        order: list[str] = []
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocker() -> str:
            started.set()
            await release.wait()
            return 'blocker'

        running = asyncio.create_task(line.run(COMPANY, blocker))
        await started.wait()

        upload = asyncio.create_task(
            line.run(COMPANY, lambda: order.append('upload') or 'upload', priority='upload')
        )
        await _until(lambda: line.pending == 1)
        quick = asyncio.create_task(
            line.run(COMPANY, lambda: order.append('quick') or 'quick', priority='quick')
        )
        await _until(lambda: line.pending == 2)

        release.set()
        await asyncio.gather(running, upload, quick)

        assert order == ['upload', 'quick']

    async def test_company_fairness_lets_another_company_go_first(self) -> None:
        line = WaitingLineAdapter(max_concurrency=2, max_per_company=1)
        order: list[str] = []
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocker() -> str:
            started.set()
            await release.wait()
            return 'a1'

        first = asyncio.create_task(line.run(COMPANY, blocker))
        await started.wait()

        second_same_company = asyncio.create_task(
            line.run(COMPANY, lambda: order.append('a2') or 'a2')
        )
        await _until(lambda: line.pending == 1)
        other_company = asyncio.create_task(
            line.run(OTHER_COMPANY, lambda: order.append('b1') or 'b1')
        )
        await _until(lambda: line.pending == 2)

        release.set()
        await asyncio.gather(first, second_same_company, other_company)

        assert order[0] == 'b1'

    async def test_results_never_mix_tenant_data(self) -> None:
        line = WaitingLineAdapter(max_concurrency=2, max_per_company=2)

        async def work(company: str) -> dict[str, str]:
            return {'company': company}

        results = await asyncio.gather(
            line.run(COMPANY, work, args=(str(COMPANY),)),
            line.run(OTHER_COMPANY, work, args=(str(OTHER_COMPANY),)),
        )

        assert [result['company'] for result in results] == [str(COMPANY), str(OTHER_COMPANY)]

    async def test_work_failure_propagates_to_the_caller(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1)

        async def broken() -> None:
            raise RuntimeError('boom')

        with pytest.raises(RuntimeError, match='boom'):
            await line.run(COMPANY, broken)

    async def test_queue_depth_cap_returns_busy_without_waiting(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1, max_queue_depth=1, max_wait_seconds=1)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocker() -> str:
            started.set()
            await release.wait()
            return 'done'

        running = asyncio.create_task(line.run(COMPANY, blocker))
        await started.wait()
        queued = asyncio.create_task(line.run(COMPANY, lambda: 'queued'))
        await _until(lambda: line.pending == 1)

        result = await line.run(COMPANY, lambda: 'overflow')

        assert isinstance(result, BusyResult)
        assert result.reason == 'queue_full'
        release.set()
        await asyncio.gather(running, queued)

    async def test_requires_company_id(self) -> None:
        line = WaitingLineAdapter(max_concurrency=1)

        with pytest.raises((TypeError, ValueError)):
            await line.run(None, lambda: 'nope')  # type: ignore[arg-type]

    async def test_invalid_ordering_fails_loudly(self) -> None:
        with pytest.raises(ValueError):
            WaitingLineAdapter(queue_priority='random')
