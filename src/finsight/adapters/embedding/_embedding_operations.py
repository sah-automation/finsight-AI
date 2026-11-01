# ruff: noqa: BLE001, PLR0912, PLR0915, TRY300, TRY301, PLC0415
"""Embedding adapter operation helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from ._embedding_helpers import _extract_vectors, _first, _resolve_config

_LOGGER = logging.getLogger(__name__)


def _resolve_aembedding() -> Any:
    # Delegate to the main module so module globals/patches are respected.
    from . import lite_llm_embedding as _main

    return _main._resolve_aembedding()


def _init_embedding(self: Any, *args: Any, **kwargs: Any) -> None:
    self.config = _resolve_config(*args, **kwargs)
    self.company_id_default = kwargs.get('company_id')
    self.embedding_func = _first(kwargs, 'embedding_func', 'aembedding', 'embed_func', default=None)

    # Resolve embedding model config.
    embedding_cfg = _first(
        kwargs, 'embedding_model', 'embedding_config', 'model_config', default=None
    )
    if embedding_cfg is None and self.config is not None:
        llm_cfg = getattr(self.config, 'llm', None)
        if llm_cfg is None:
            llm_cfg = getattr(self.config, 'llm_config', None)
        if llm_cfg is not None:
            embedding_cfg = getattr(llm_cfg, 'embedding_model', None)
        if embedding_cfg is None and self.config is not None:
            embedding_cfg = getattr(self.config, 'embedding', None)
        if embedding_cfg is None and self.config is not None:
            embedding_cfg = getattr(self.config, 'embedding_model', None)

    model_id = _first(kwargs, 'model_id', 'model', default=None)
    if model_id is None and embedding_cfg is not None:
        model_id = getattr(embedding_cfg, 'model_id', None)
        if model_id is None and isinstance(embedding_cfg, dict):
            model_id = embedding_cfg.get('model_id') or embedding_cfg.get('model')
    if model_id is None:
        model_id = 'default-embedding'
    self.model_id = str(model_id)

    dimensions = _first(kwargs, 'dimensions', 'embedding_dimensions', default=None)
    if dimensions is None and embedding_cfg is not None:
        dimensions = getattr(embedding_cfg, 'dimensions', None)
        if dimensions is None and isinstance(embedding_cfg, dict):
            dimensions = embedding_cfg.get('dimensions')
    self.dimensions = int(dimensions) if dimensions is not None else 0

    batch_size = _first(kwargs, 'batch_size', default=None)
    if batch_size is None and embedding_cfg is not None:
        batch_size = getattr(embedding_cfg, 'batch_size', None)
        if batch_size is None and isinstance(embedding_cfg, dict):
            batch_size = embedding_cfg.get('batch_size')
    self.batch_size = int(batch_size) if batch_size is not None else 16
    self.batch_size = max(self.batch_size, 1)

    timeout = _first(kwargs, 'timeout_seconds', 'timeout', default=None)
    if timeout is None and embedding_cfg is not None:
        timeout = getattr(embedding_cfg, 'timeout_seconds', None)
        if timeout is None and isinstance(embedding_cfg, dict):
            timeout = embedding_cfg.get('timeout_seconds')
    self.timeout = int(timeout) if timeout is not None else 30

    max_retries = _first(kwargs, 'max_retries', 'retry_attempts', default=None)
    if max_retries is None and embedding_cfg is not None:
        max_retries = getattr(
            embedding_cfg, 'max_retries', getattr(embedding_cfg, 'retry_attempts', None)
        )
        if max_retries is None and isinstance(embedding_cfg, dict):
            max_retries = embedding_cfg.get('max_retries', embedding_cfg.get('retry_attempts'))
    self.max_retries = int(max_retries) if max_retries is not None else 3

    retry_wait = _first(
        kwargs,
        'retry_wait_seconds',
        'retry_base_delay_seconds',
        'retry_delay_seconds',
        default=None,
    )
    if retry_wait is None and embedding_cfg is not None:
        retry_wait = getattr(
            embedding_cfg,
            'retry_wait_seconds',
            getattr(embedding_cfg, 'retry_base_delay_seconds', None),
        )
        if retry_wait is None and isinstance(embedding_cfg, dict):
            retry_wait = embedding_cfg.get(
                'retry_wait_seconds', embedding_cfg.get('retry_base_delay_seconds')
            )
    self.retry_wait = float(retry_wait) if retry_wait is not None else 2.0

    self.metering = _first(
        kwargs,
        'metering',
        'meter',
        'metering_service',
        'usage_meter',
        'usage_recorder',
        'record_usage',
        'metric_recorder',
        default=None,
    )
    self.logger = _first(kwargs, 'logger', default=_LOGGER)
    self.usage_rows = []
    self._usage_lock = asyncio.Lock()


async def _embed_batch(self: Any, texts: list[str]) -> list[list[float]]:
    attempts = self.max_retries + 1
    delay = self.retry_wait
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            fn = self.embedding_func
            if not callable(fn):
                fn = _resolve_aembedding()
            kwargs = {
                'model': self.model_id,
                'input': texts,
                'timeout': self.timeout,
            }
            result = fn(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            vectors = _extract_vectors(result)
            if self.dimensions:
                for vector in vectors:
                    if len(vector) != self.dimensions:
                        raise ValueError(
                            f'Expected {self.dimensions} dimensions, got {len(vector)}'
                        )
            return vectors
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
    raise last_error if last_error is not None else RuntimeError('embedding failed')


async def _record_usage(
    self: Any, model_id: str, company_id: Any, units: int, trace_id: Any = None
) -> None:
    import uuid

    if trace_id is None:
        trace_id = str(uuid.uuid4())
    row = {
        'company_id': company_id,
        'service': 'embedding',
        'units': units,
        'estimated_cost': None,
        'cost': None,
        'model': model_id,
        'model_name': model_id,
        'trace_id': trace_id,
        'trace': trace_id,
        'trace_identifier': trace_id,
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
            service='embedding',
            model=r['model'],
            model_name=r['model'],
            units=r['units'],
            estimated_cost=r['estimated_cost'],
            cost=r['cost'],
            trace_id=r['trace_id'],
            trace=r['trace'],
            trace_identifier=r['trace_identifier'],
            usage=r,
            row=r,
        ),
        lambda m=method, r=row: m(r),
        lambda m=method, r=row: m(
            r['company_id'], 'embedding', r['units'], None, r['model'], r['trace_id']
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


# alias methods
