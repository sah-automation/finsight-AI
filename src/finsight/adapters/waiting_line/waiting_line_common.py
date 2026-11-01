"""Shared helpers for waiting-line adapters."""

from __future__ import annotations

import inspect
from typing import Any


def company(company_id: object) -> str:
    value = '' if company_id is None else str(company_id).strip()
    if not value:
        raise ValueError('company_id is required for the waiting line')
    return value


async def invoke(work: object, args: tuple[object, ...], kwargs: dict[str, object]) -> object:
    if work is None:
        return None
    if inspect.isawaitable(work):
        return await work
    if callable(work):
        result = work(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
    return work


def parse_work(
    args: tuple[object, ...], values: dict[str, Any]
) -> tuple[object, tuple[object, ...], dict[str, object]]:
    work = values.pop('work', None)
    for key in ('operation', 'fn', 'func', 'callable'):
        if work is None:
            work = values.pop(key, None)
    work_args = tuple(values.pop('args', ()) or ())
    work_kwargs = dict(values.pop('kwargs', {}) or {})
    if work is None and args:
        work = args[0]
        work_args = tuple(args[1:]) or work_args
    return work, work_args, work_kwargs
