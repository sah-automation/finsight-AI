# ruff: noqa: PLR0913, TRY300
"""Reranker adapter operation helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Iterable, Sequence
from typing import Any

from ._rerank_helpers import (
    _attach_score,
    _candidate_text,
    _candidate_value,
    _company,
    _config_value,
    _first,
    _float,
    _local_score,
    _resolve_config,
    _score_items,
    _text,
)
from .rerank_result import RerankResult

_LOGGER = logging.getLogger(__name__)


def _init_reranker(self: Any, *args: Any, **kwargs: Any) -> None:
    self.config = kwargs.get('config') or _resolve_config(*args, **kwargs)
    config = self.config
    raw_client = None
    if isinstance(kwargs, dict):
        raw_client = _first(kwargs, 'client', 'scorer', 'reranker', 'cohere_client', default=None)
    self.client = raw_client
    self.model = _text(_first(kwargs, 'model', default=_config_value(config, 'model')))
    self.provider = _text(
        _first(kwargs, 'provider', default=_config_value(config, 'provider', default='local'))
    )
    self.top_n = int(
        _first(kwargs, 'top_n', default=_config_value(config, 'top_n', default=20)) or 20
    )
    self.batch_size = max(
        1,
        int(
            _first(kwargs, 'batch_size', default=_config_value(config, 'batch_size', default=50))
            or 50
        ),
    )
    self.timeout_seconds = _float(
        _first(
            kwargs,
            'timeout_seconds',
            default=_config_value(config, 'timeout_seconds', default=10),
        ),
        10.0,
    )
    self.max_retries = int(
        _first(kwargs, 'max_retries', default=_config_value(config, 'max_retries', default=0)) or 0
    )
    self.enabled = bool(
        _first(
            kwargs,
            'reranker_enabled',
            'enabled',
            default=_config_value(config, 'reranker_enabled', default=True),
        )
    )
    self.evidence_threshold = _float(
        _first(
            kwargs,
            'evidence_min_score',
            default=_config_value(config, 'evidence_min_score', default=0.30),
        ),
        0.30,
    )
    self.search_score_threshold = _float(
        _first(
            kwargs,
            'evidence_min_search_score',
            default=_config_value(config, 'evidence_min_search_score', default=0.50),
        ),
        0.50,
    )


def _metering_model_id(self: Any) -> str:
    """Provider-qualified model id (``{provider}/{model}``) used for metering.

    The price table and approved-model rules key the provider-qualified id,
    while the provider-facing wire name keeps its prefix-stripped form. Only
    metering and pricing consumers use this id (issue #261).
    """
    provider = _text(getattr(self, 'provider', '') or '')
    model = _text(getattr(self, 'model', '') or '')
    if provider and model and not model.startswith(f'{provider}/'):
        return f'{provider}/{model}'
    return model or provider


async def _rerank(self: Any, company_id: object, *args: Any, **kwargs: Any) -> Any:
    company = _company(company_id)
    values: dict[str, Any] = dict(kwargs)
    question, candidates = _parse(args, values)
    candidates = _tenant_candidates(company, candidates)
    if not candidates:
        return _result(self, [], fallback=False, threshold=self.evidence_threshold)
    if not self.enabled:
        return _fallback(self, company, candidates, disabled=True)
    try:
        scored = await _score(self, company, question, candidates)
    except Exception as exc:
        _LOGGER.exception(
            'reranker fallback to search order',
            extra={
                'alert': 'reranker_down',
                'reranker_down': True,
                'company_id': company,
                'fallback_mode': 'search_order',
                'error': str(exc),
            },
        )
        return _fallback(self, company, candidates)
    top_n = int(_first(values, 'top_n', 'limit', default=self.top_n) or self.top_n)
    ordered = sorted(scored, key=lambda item: (-item[1], item[0]))[: max(1, top_n)]
    results = [_attach_score(candidates[index], score) for index, score in ordered]
    return _result(
        self,
        results,
        fallback=False,
        threshold=self.evidence_threshold,
        batch_count=_batch_count(self, len(candidates)),
    )


def _parse(args: tuple[object, ...], values: dict[str, Any]) -> tuple[str, list[Any]]:
    question = _text(_first(values, 'question', 'query', 'text'))
    candidates = _first(values, 'candidates', 'results', 'documents', 'chunks')
    for arg in args:
        if isinstance(arg, str) and not question:
            question = arg
        elif isinstance(arg, dict) and candidates is None:
            candidates = [arg]
        elif isinstance(arg, Iterable) and not isinstance(arg, (str, bytes)):
            candidates = list(arg)
    return question, list(candidates or [])


def _tenant_candidates(company: str, candidates: Sequence[Any]) -> list[Any]:
    filtered = []
    for candidate in candidates:
        candidate_company = _text(_candidate_value(candidate, 'company_id', 'tenant_id'))
        if candidate_company and candidate_company != company:
            continue
        filtered.append(candidate)
    return filtered


def _batch_count(self: Any, size: int) -> int:
    return int((size + self.batch_size - 1) // self.batch_size)


async def _score(
    self: Any, company: str, question: str, candidates: list[Any]
) -> list[tuple[int, float]]:
    scored: list[tuple[int, float]] = []
    for start in range(0, len(candidates), self.batch_size):
        batch = candidates[start : start + self.batch_size]
        scores = await _score_batch(self, company, question, batch)
        scored.extend((start + index, score) for index, score in enumerate(scores))
    return scored


async def _score_batch(self: Any, company: str, question: str, batch: list[Any]) -> list[float]:
    last_error: Exception | None = None
    for _attempt in range(self.max_retries + 1):
        try:
            response = await asyncio.wait_for(
                _call_scorer(self, company, question, batch), timeout=self.timeout_seconds
            )
            return _score_items(response, len(batch))
        except Exception as exc:
            last_error = exc
    if self.client is None:
        return [_local_score(question, candidate) for candidate in batch]
    raise last_error or RuntimeError('reranker failed')


async def _call_scorer(self: Any, company: str, question: str, batch: list[Any]) -> object:
    if self.client is None:
        return [_local_score(question, candidate) for candidate in batch]
    documents = [_candidate_text(candidate) for candidate in batch]
    attempts = _scorer_attempts(self, company, question, batch, documents)
    last_error: TypeError | None = None
    for attempt in attempts:
        try:
            result = attempt()
            if inspect.isawaitable(result):
                result = await result
            return result
        except TypeError as exc:
            last_error = exc
            continue
    raise last_error or TypeError('reranker client has no usable method')


def _scorer_attempts(
    self: Any, company: str, question: str, batch: list[Any], documents: list[str]
) -> list[Any]:
    attempts: list[Any] = []
    client = self.client
    for name in ('rerank', 'score', 'rank', 'rerank_candidates', 'acompletion'):
        method = getattr(client, name, None)
        if not callable(method):
            continue
        attempts.append(
            lambda method=method: method(
                model=self.model,
                query=question,
                documents=documents,
                top_n=len(documents),
                company_id=company,
            )
        )
        attempts.append(lambda method=method: method(question, batch))
        attempts.append(lambda method=method: method(question, documents))
    if callable(client):
        attempts.append(lambda: client(question, batch))
        attempts.append(lambda: client(question, documents))
    return attempts


def _fallback(
    self: Any, company: str, candidates: list[Any], *, disabled: bool = False
) -> RerankResult:
    trace = {
        'reranker_fallback': True,
        'reranker_disabled': disabled,
        'fallback_mode': 'search_order',
        'evidence_threshold': self.search_score_threshold,
        'company_id': company,
    }
    return _result(
        self,
        candidates,
        fallback=True,
        threshold=self.search_score_threshold,
        trace=trace,
        disabled=disabled,
    )


def _result(
    self: Any,
    candidates: list[Any],
    *,
    fallback: bool,
    threshold: float,
    trace: dict[str, Any] | None = None,
    disabled: bool = False,
    batch_count: int = 0,
) -> RerankResult:

    return RerankResult(
        candidates,
        fallback=fallback,
        disabled=disabled,
        fallback_mode='search_order' if fallback else None,
        threshold=threshold,
        trace=trace or {'reranker_fallback': False, 'evidence_threshold': threshold},
        batch_count=batch_count,
        model=self.model,
        provider=self.provider,
    )
