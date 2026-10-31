# ruff: noqa: BLE001, PLR2004, TRY300
"""LLM gateway usage and chain helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


async def _record_usage(
    self: Any, model_id: str, company_id: Any, trace_id: Any = None, units: int = 1
) -> None:
    row = {
        'company_id': company_id,
        'service': 'llm',
        'units': units,
        'estimated_cost': None,
        'model': model_id,
        'model_name': model_id,
        'trace_id': trace_id,
        'trace': trace_id,
    }
    async with self._usage_lock:
        self.usage_rows.append(row)
    await _invoke_metering(self, row)


async def _invoke_metering(self: Any, row: dict[str, Any]) -> None:
    target = self.metering
    if target is None:
        return
    if callable(target) and not hasattr(target, 'record_usage') and not hasattr(target, 'record'):
        try:
            result = target(row)
            if inspect.isawaitable(result):
                await result
            return
        except Exception:
            _LOGGER.debug('metering callable failed', exc_info=True)
    method = None
    for name in (
        'record_usage',
        'record',
        'usage',
        'track_usage',
        'write_usage',
        'meter',
        'meter_call',
        'on_usage',
    ):
        candidate = getattr(target, name, None)
        if callable(candidate):
            method = candidate
            break
    if method is None:
        return
    attempts = [
        lambda m=method, r=row: m(
            company_id=r['company_id'],
            service='llm',
            model=r['model'],
            model_name=r['model'],
            units=r['units'],
            estimated_cost=r['estimated_cost'],
            trace_id=r['trace_id'],
            trace=r['trace_id'],
            usage=r,
            row=r,
        ),
        lambda m=method, r=row: m(r),
        lambda m=method, r=row: m(
            r['company_id'], 'llm', r['units'], None, r['model'], r['trace_id']
        ),
    ]
    for attempt in attempts:
        try:
            result = attempt()  # type: ignore[no-untyped-call]
            if inspect.isawaitable(result):
                await result
            return
        except TypeError:
            continue
        except Exception:
            _LOGGER.debug('metering method failed', exc_info=True)
            return


def _alert_fallback_3(self: Any, model_id: str, company_id: Any) -> None:
    self.fallback_3_used = True
    self._last_trace['fallback_3_used'] = True
    self._last_trace['fallback_3_model'] = model_id
    self._tags.append({'tag': 'fallback_3_used', 'model': model_id})
    callback = self.on_fallback_3
    if callable(callback):
        try:
            result = callback(model_id, company_id=company_id, tag='fallback_3_used')
            if inspect.isawaitable(result):
                asyncio.ensure_future(result)  # noqa: RUF006
        except Exception:
            _LOGGER.debug('fallback 3 alert callback failed', exc_info=True)
        return
    try:
        self.logger.warning(
            'Fallback 3 used: %s',
            model_id,
            extra={
                'fallback_3_used': True,
                'fallback_3_model': model_id,
                'tag': 'fallback_3_used',
                'model': model_id,
            },
        )
    except Exception:
        _LOGGER.warning('Fallback 3 used: %s', model_id)


def _choose_chain(self: Any, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    chain_name = kwargs.get('chain') or kwargs.get('model_chain') or kwargs.get('chain_name')
    if chain_name is not None and str(chain_name) in self.chains:
        return list(self.chains[str(chain_name)])
    if (
        kwargs.get('cheap') or kwargs.get('use_cheap') or kwargs.get('cheap_mode')
    ) and 'cheap' in self.chains:
        return list(self.chains['cheap'])
    has_calculation = bool(kwargs.get('has_calculation') or kwargs.get('calculation_intent'))
    if has_calculation and 'primary' in self.chains:
        return list(self.chains['primary'])
    estimated_size = kwargs.get('estimated_input_tokens') or kwargs.get('input_size')
    if (
        isinstance(estimated_size, (int, float))
        and estimated_size > 4000
        and 'primary' in self.chains
    ):
        return list(self.chains['primary'])
    route = kwargs.get('route') or kwargs.get('model_route')
    if isinstance(route, str) and route in self.chains:
        return list(self.chains[route])
    return list(self.chains.get(self.default_chain_name, next(iter(self.chains.values()))))


def _extract_company_id(self: Any, value: Any, kwargs: dict[str, Any]) -> Any:
    if value is not None:
        return value
    if kwargs.get('company_id') is not None:
        return kwargs.get('company_id')
    if self.company_id_default is not None:
        return self.company_id_default
    return kwargs.get('tenant_id') or kwargs.get('company') or 'unknown'
