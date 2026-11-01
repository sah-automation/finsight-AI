"""Pass-through waiting line: runs submitted work directly (no queue, no caps)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from finsight.domain.ports.waiting_line import WaitingLine as WaitingLinePort

from .waiting_line_common import (
    company as _company,
)
from .waiting_line_common import (
    invoke as _invoke,
)
from .waiting_line_common import (
    parse_work as _parse_work_common,
)

_LOGGER = logging.getLogger(__name__)


class PassthroughWaitingLine(WaitingLinePort):
    """Run heavy work directly, without queueing or concurrency caps."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Accept configuration/kwargs for interface compatibility, but do not
        # gate execution on them.
        self._config = kwargs.get('config')
        if self._config is None:
            for arg in args:
                if isinstance(arg, Mapping) or hasattr(arg, 'switches'):
                    self._config = arg
                    break
        self.settings = None

    @property
    def pending(self) -> int:
        return 0

    @property
    def active(self) -> int:
        return 0

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self._run_impl(*args, **kwargs)

    async def _run_impl(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        _company(company_id)
        values: dict[str, Any] = dict(kwargs)
        work, work_args, work_kwargs = self._parse_work(args, values)
        # Drop waiting-line-specific scheduling hints.
        values.pop('priority', None)
        values.pop('work_priority', None)
        work_kwargs = {**work_kwargs, **values}
        return await _invoke(work, work_args, work_kwargs)

    @staticmethod
    def _parse_work(
        args: tuple[object, ...], values: dict[str, Any]
    ) -> tuple[object, tuple[object, ...], dict[str, object]]:
        return _parse_work_common(args, values)


NoOpWaitingLine = PassthroughWaitingLine
PassThroughWaitingLine = PassthroughWaitingLine

__all__ = ['NoOpWaitingLine', 'PassThroughWaitingLine', 'PassthroughWaitingLine']
