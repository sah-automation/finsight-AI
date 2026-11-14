"""Bounded waiting line around heavy work.

Heavy Q&A steps enter the line through :meth:`WaitingLineAdapter.run`. The line
caps how many jobs run at once, keeps one company from taking every slot, orders
work either quick-first or by arrival, and returns a friendly :class:`BusyResult`
when a request waits longer than the configured limit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from finsight.core.logging import get_trace_id
from finsight.domain.ports.waiting_line import WaitingLine as WaitingLinePort

from .busy_result import BusyResult
from .waiting_line_common import (
    company as _company,
)
from .waiting_line_common import (
    invoke as _invoke,
)
from .waiting_line_common import (
    parse_work as _parse_work_common,
)
from .waiting_line_job import WaitingLineJob
from .waiting_line_settings import WaitingLineSettings, priority_rank

_LOGGER = logging.getLogger(__name__)


class WaitingLineAdapter(WaitingLinePort):
    """Run heavy work with ordering, caps, fairness and a busy timeout.

    The adapter is process-local. It is deliberately small: a concurrency cap,
    a per-company cap, a short queue and a timeout are enough to protect the
    ask flow without adding a second durable queue.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.settings = WaitingLineSettings.from_kwargs(args, kwargs)
        self.max_concurrency = self.settings.max_concurrency
        self.max_per_company = self.settings.max_per_company
        self.max_wait_seconds = self.settings.max_wait_seconds
        self.queue_priority = self.settings.queue_priority
        self.max_queue_depth = self.settings.max_queue_depth

        self._queue: list[WaitingLineJob] = []
        self._active: dict[str, int] = {}
        self._active_total = 0
        self._sequence = 0
        self._last_company: str | None = None
        self._lock = asyncio.Lock()
        self._slot_free = asyncio.Event()
        self._dispatcher: asyncio.Task[None] | None = None
        self._workers: set[asyncio.Task[None]] = set()

    @property
    def pending(self) -> int:
        """Number of jobs waiting for a slot (not currently running)."""
        return len(self._queue)

    @property
    def active(self) -> int:
        """Number of jobs currently running."""
        return self._active_total

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self._run_impl(*args, **kwargs)

    async def _run_impl(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        company = _company(company_id)
        values: dict[str, Any] = dict(kwargs)
        work, work_args, work_kwargs = self._parse_work(args, values)
        priority = priority_rank(values.pop('priority', values.pop('work_priority', None)))
        work_kwargs = {**work_kwargs, **values}
        if self.max_queue_depth > 0 and len(self._queue) >= self.max_queue_depth:
            _LOGGER.warning(
                'waiting line queue full',
                extra={'company_id': company, 'queue_priority': self.queue_priority},
            )
            return self._busy(company, 'queue_full', wait_seconds=0.0)

        loop = asyncio.get_running_loop()
        self._sequence += 1
        job = WaitingLineJob(
            company=company,
            priority=priority,
            sequence=self._sequence,
            enqueued_at=loop.time(),
            work=work,
            args=work_args,
            kwargs=work_kwargs,
            future=loop.create_future(),
        )
        async with self._lock:
            self._queue.append(job)
            self._ensure_dispatcher()

        try:
            return await asyncio.wait_for(asyncio.shield(job.future), timeout=self.max_wait_seconds)
        except TimeoutError:
            if await self._expire(job):
                return await job.future
            wait_seconds = loop.time() - job.enqueued_at
            _LOGGER.warning(
                'waiting line busy',
                extra={
                    'company_id': company,
                    'wait_seconds': wait_seconds,
                    'queue_priority': self.queue_priority,
                    'trace_id': get_trace_id(),
                },
            )
            return self._busy(company, 'timeout', wait_seconds=wait_seconds)

    @staticmethod
    def _parse_work(
        args: tuple[object, ...], values: dict[str, Any]
    ) -> tuple[object, tuple[object, ...], dict[str, object]]:
        return _parse_work_common(args, values)

    def _ensure_dispatcher(self) -> None:
        if self._dispatcher is None or self._dispatcher.done():
            self._dispatcher = asyncio.create_task(self._dispatch())

    async def _dispatch(self) -> None:
        while True:
            wait = False
            job: WaitingLineJob | None = None
            async with self._lock:
                if not self._queue:
                    self._dispatcher = None
                    return
                job = self._pick_locked()
                if job is None:
                    self._slot_free.clear()
                    wait = True
                else:
                    self._queue.remove(job)
                    self._active_total += 1
                    self._active[job.company] = self._active.get(job.company, 0) + 1
                    self._last_company = job.company
            if wait:
                await self._slot_free.wait()
                continue
            if job is not None:
                self._start_worker(job)

    def _start_worker(self, job: WaitingLineJob) -> None:
        task = asyncio.create_task(self._run_job(job))
        self._workers.add(task)
        task.add_done_callback(self._workers.discard)

    def _pick_locked(self) -> WaitingLineJob | None:
        if self._active_total >= self.max_concurrency:
            return None
        eligible = [
            job for job in self._queue if self._active.get(job.company, 0) < self.max_per_company
        ]
        if not eligible:
            return None
        if self.queue_priority == 'first_come':
            return min(eligible, key=lambda job: job.sequence)
        return min(
            eligible,
            key=lambda job: (
                job.priority,
                0 if job.company != self._last_company else 1,
                job.sequence,
            ),
        )

    async def _run_job(self, job: WaitingLineJob) -> None:
        wait_seconds = asyncio.get_running_loop().time() - job.enqueued_at
        _LOGGER.info(
            'waiting line started',
            extra={
                'company_id': job.company,
                'wait_seconds': wait_seconds,
                'queue_priority': self.queue_priority,
                'trace_id': get_trace_id(),
            },
        )
        try:
            result = await _invoke(job.work, job.args, job.kwargs)
        except asyncio.CancelledError:
            if not job.future.done():
                job.future.cancel()
            raise
        except BaseException as exc:  # re-raised on the caller's future
            if not job.future.done():
                job.future.set_exception(exc)
        else:
            if not job.future.done():
                job.future.set_result(result)
        finally:
            await self._release(job.company)

    async def _release(self, company: str) -> None:
        async with self._lock:
            self._active_total = max(0, self._active_total - 1)
            remaining = self._active.get(company, 0) - 1
            if remaining > 0:
                self._active[company] = remaining
            else:
                self._active.pop(company, None)
        self._slot_free.set()
        self._ensure_dispatcher()

    async def _expire(self, job: WaitingLineJob) -> bool:
        """Remove a queued job on timeout; return True when it already started."""
        async with self._lock:
            if job in self._queue:
                self._queue.remove(job)
                if not job.future.done():
                    job.future.cancel()
                return False
        return True

    def _busy(self, company: str, reason: str, *, wait_seconds: float) -> BusyResult:
        return BusyResult(
            company_id=company,
            reason=reason,
            retry_after_seconds=min(1.0, max(0.1, self.max_wait_seconds)),
            wait_seconds=wait_seconds,
            queue_priority=self.queue_priority,
            details={
                'max_concurrency': self.max_concurrency,
                'max_per_company': self.max_per_company,
                'max_queue_depth': self.max_queue_depth,
            },
        )


# Naming variants used across the project.
FairWaitingLine = WaitingLineAdapter
QueueLineAdapter = WaitingLineAdapter

__all__ = ['FairWaitingLine', 'QueueLineAdapter', 'WaitingLineAdapter']
