"""Cross-encoder reranker with a safe search-order fallback.

Candidates are scored in configured batches. Any provider error, timeout or
exhausted retry budget returns the original search order, tags the trace, raises
an alert and switches the evidence threshold to the configured search-score
threshold.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Any, cast

from finsight.domain.ports.reranker import Reranker as RerankerPort

from .rerank_result import RerankResult

_LOGGER = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r'[a-z0-9]+')
_STOPWORDS = frozenset(
    {
        'a',
        'an',
        'and',
        'are',
        'as',
        'at',
        'be',
        'by',
        'for',
        'in',
        'is',
        'of',
        'on',
        'or',
        'the',
        'to',
        'was',
        'were',
    }
)


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _first(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if values.get(name) is not None:
            return values.get(name)
    return default


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('switches', 'reranker', 'retrieval', 'search')
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                nested = config.get(section)
                if isinstance(nested, dict) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
                nested = getattr(config, section, None)
                value = (
                    nested.get(name) if isinstance(nested, dict) else getattr(nested, name, None)
                )
                if value is not None:
                    return value
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if any(hasattr(arg, attr) for attr in ('reranker', 'retrieval', 'switches', 'app')):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        config = getattr(container, 'config', None) if container is not None else None
        if config is not None:
            return config
    return None


def _company(company_id: object) -> str:
    value = _text(company_id).strip()
    if not value:
        raise ValueError('company_id is required for reranking')
    return value


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _candidate_value(candidate: object, *names: str) -> object:
    if isinstance(candidate, dict):
        for name in names:
            if candidate.get(name) is not None:
                return candidate.get(name)
        return None
    for name in names:
        if hasattr(candidate, name):
            return getattr(candidate, name)
    return None


def _candidate_text(candidate: object) -> str:
    return _text(
        _candidate_value(candidate, 'text', 'content', 'chunk_text', 'document', 'page_content')
    )


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _local_score(question: str, candidate: object) -> float:
    query_tokens = _tokens(question)
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(_candidate_text(candidate))) / len(query_tokens)


def _attach_score(candidate: object, score: float) -> object:
    if isinstance(candidate, dict):
        candidate['rerank_score'] = score
        candidate['score'] = score
        return candidate
    target = cast('Any', candidate)
    try:
        target.rerank_score = score
        target.score = score
    except (AttributeError, TypeError):
        pass
    return candidate


def _score_items(response: object, size: int) -> list[float]:
    if response is None:
        return [0.0] * size
    if isinstance(response, dict):
        for key in ('results', 'data', 'scores'):
            if key in response:
                return _score_items(response[key], size)
        return [0.0] * size
    for attr in ('results', 'data', 'scores'):
        value = getattr(response, attr, None)
        if value is not None:
            return _score_items(value, size)
    if not isinstance(response, Iterable) or isinstance(response, (str, bytes)):
        return [0.0] * size
    items = list(response)
    scores = [0.0] * size
    for position, item in enumerate(items):
        index = position
        score = item
        if isinstance(item, dict):
            index = int(item.get('index', item.get('document_index', position)) or position)
            score = item.get('relevance_score', item.get('score', item.get('value', 0.0)))
        elif not isinstance(item, (int, float)):
            index = int(getattr(item, 'index', getattr(item, 'document_index', position)))
            score = getattr(
                item, 'relevance_score', getattr(item, 'score', getattr(item, 'value', 0.0))
            )
        if 0 <= index < size:
            scores[index] = _float(score)
    return scores


class CohereReranker(RerankerPort):
    """Score candidates in batches and fall back to search order on failure."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = kwargs.get('config') or _resolve_config(*args, **kwargs)
        self.client = _first(kwargs, 'client', 'scorer', 'reranker', 'cohere_client')
        config = self.config
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
                _first(
                    kwargs, 'batch_size', default=_config_value(config, 'batch_size', default=50)
                )
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
            _first(kwargs, 'max_retries', default=_config_value(config, 'max_retries', default=0))
            or 0
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

    async def rerank(self, company_id: object, *args: object, **kwargs: object) -> RerankResult:
        company = _company(company_id)
        values: dict[str, Any] = dict(kwargs)
        question, candidates = self._parse(args, values)
        candidates = self._tenant_candidates(company, candidates)
        if not candidates:
            return self._result([], fallback=False, threshold=self.evidence_threshold)
        if not self.enabled:
            return self._fallback(company, candidates, disabled=True)
        try:
            scored = await self._score(company, question, candidates)
        except Exception as exc:
            _LOGGER.exception(
                'reranker fallback to search order',
                extra={
                    'alert': 'reranker_down',
                    'company_id': company,
                    'fallback_mode': 'search_order',
                    'error': str(exc),
                },
            )
            return self._fallback(company, candidates)
        top_n = int(_first(values, 'top_n', 'limit', default=self.top_n) or self.top_n)
        ordered = sorted(scored, key=lambda item: (-item[1], item[0]))[: max(1, top_n)]
        results = [_attach_score(candidates[index], score) for index, score in ordered]
        return self._result(
            results,
            fallback=False,
            threshold=self.evidence_threshold,
            batch_count=self._batch_count(len(candidates)),
        )

    @staticmethod
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

    @staticmethod
    def _tenant_candidates(company: str, candidates: Sequence[Any]) -> list[Any]:
        filtered = []
        for candidate in candidates:
            candidate_company = _text(_candidate_value(candidate, 'company_id', 'tenant_id'))
            if candidate_company and candidate_company != company:
                continue
            filtered.append(candidate)
        return filtered

    def _batch_count(self, size: int) -> int:
        return (size + self.batch_size - 1) // self.batch_size

    async def _score(
        self, company: str, question: str, candidates: list[Any]
    ) -> list[tuple[int, float]]:
        scored: list[tuple[int, float]] = []
        for start in range(0, len(candidates), self.batch_size):
            batch = candidates[start : start + self.batch_size]
            scores = await self._score_batch(company, question, batch)
            scored.extend((start + index, score) for index, score in enumerate(scores))
        return scored

    async def _score_batch(self, company: str, question: str, batch: list[Any]) -> list[float]:
        last_error: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self._call_scorer(company, question, batch), timeout=self.timeout_seconds
                )
                return _score_items(response, len(batch))
            except Exception as exc:
                last_error = exc
        if self.client is None:
            return [_local_score(question, candidate) for candidate in batch]
        raise last_error or RuntimeError('reranker failed')

    async def _call_scorer(self, company: str, question: str, batch: list[Any]) -> object:
        if self.client is None:
            return [_local_score(question, candidate) for candidate in batch]
        documents = [_candidate_text(candidate) for candidate in batch]
        attempts = self._scorer_attempts(company, question, batch, documents)
        last_error: TypeError | None = None
        for attempt in attempts:
            try:
                result = attempt()
                if inspect.isawaitable(result):
                    result = await result
            except TypeError as exc:
                last_error = exc
                continue
            return result
        raise last_error or TypeError('reranker client has no usable method')

    def _scorer_attempts(
        self, company: str, question: str, batch: list[Any], documents: list[str]
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
        self, company: str, candidates: list[Any], *, disabled: bool = False
    ) -> RerankResult:
        trace = {
            'reranker_fallback': True,
            'reranker_disabled': disabled,
            'fallback_mode': 'search_order',
            'evidence_threshold': self.search_score_threshold,
            'company_id': company,
        }
        return self._result(
            candidates,
            fallback=True,
            threshold=self.search_score_threshold,
            trace=trace,
            disabled=disabled,
        )

    def _result(  # noqa: PLR0913 - result metadata is explicit
        self,
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


__all__ = ['CohereReranker']
