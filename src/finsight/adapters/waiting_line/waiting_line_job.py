"""One queued unit of work inside the waiting line."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


class WaitingLineJob:
    """A unit of work waiting for a concurrency slot."""

    def __init__(
        self,
        *,
        company: str,
        priority: int,
        sequence: int,
        enqueued_at: float,
        work: object,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        future: asyncio.Future[object],
    ) -> None:
        self.company = company
        self.priority = priority
        self.sequence = sequence
        self.enqueued_at = enqueued_at
        self.work = work
        self.args = args
        self.kwargs = kwargs
        self.future = future


__all__ = ['WaitingLineJob']
