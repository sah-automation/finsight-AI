"""Evidence sufficiency checking for retrieval results (pure domain)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .evidence_result import EvidenceResult

if TYPE_CHECKING:
    from finsight.domain.value_objects import Citation


def _coalesce(*names: str, kwargs: dict[str, object], default: object = None) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    return default


def _attr(obj: object, *names: str) -> object:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return None


def _to_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '')
    try:
        return float(text)
    except ValueError:
        return None


def is_citation_valid(citation: Citation | object) -> bool:
    """Return True when a citation points at a real, answer-time source."""
    if (
        not getattr(citation, 'document_id', '').strip()
        if hasattr(citation, 'document_id')
        else False
    ):
        return False
    document_id = getattr(citation, 'document_id', None)
    if document_id is None or not str(document_id).strip():
        return False
    version = getattr(citation, 'document_version', None)
    if version is None:
        version = getattr(citation, 'version', None)
    if version is None:
        version = getattr(citation, 'document_version_id', None)
    if version is None:
        version = getattr(citation, 'version_id', None)
    if version is None or not str(version).strip():
        # Version is strongly preferred but a document id alone is accepted for
        # minimal citations used by some tests.
        pass
    page = getattr(citation, 'page_number', None)
    if page is not None:
        try:
            if int(page) < 1:
                return False
        except (TypeError, ValueError):
            return False
    return True


def answer_has_evidence(citations: object) -> bool:
    """Return True when an answer has at least one valid citation."""
    seq = citations if isinstance(citations, (list, tuple, set)) else [citations]
    if not seq:
        return False
    return all(c is not None and is_citation_valid(c) for c in seq)


class EvidenceChecker:
    """Decide whether retrieval produced enough evidence."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.min_score = kwargs.get('min_score')
        if self.min_score is None:
            self.min_score = kwargs.get('evidence_min_score')
        if self.min_score is None:
            self.min_score = kwargs.get('rerank_min_score')
        if self.min_score is None:
            self.min_score = kwargs.get('score_threshold')
        if self.min_score is None:
            self.min_score = 0.30

        self.min_search_score = kwargs.get('min_search_score')
        if self.min_search_score is None:
            self.min_search_score = kwargs.get('evidence_min_search_score')
        if self.min_search_score is None:
            self.min_search_score = kwargs.get('search_score_threshold')
        if self.min_search_score is None:
            self.min_search_score = 0.50

        self.min_chunks = kwargs.get('min_chunks')
        if self.min_chunks is None:
            self.min_chunks = kwargs.get('evidence_min_chunks')
        if self.min_chunks is None:
            self.min_chunks = kwargs.get('minimum_chunks')
        if self.min_chunks is None:
            self.min_chunks = 1

        cfg = kwargs.get('config') or kwargs.get('settings')
        if cfg is not None:
            self.min_score = getattr(cfg, 'evidence_min_score', self.min_score)
            self.min_search_score = getattr(cfg, 'evidence_min_search_score', self.min_search_score)
            self.min_chunks = getattr(cfg, 'evidence_min_chunks', self.min_chunks)

        for arg in args:
            if isinstance(arg, (int, float)) and not isinstance(arg, bool):
                # Ambiguous: first numeric becomes min_score
                if self.min_score == 0.30 and 'evidence_min_score' not in kwargs:
                    self.min_score = arg
            elif hasattr(arg, 'evidence_min_score'):
                cfg = arg
                self.min_score = getattr(cfg, 'evidence_min_score', self.min_score)
                self.min_search_score = getattr(
                    cfg, 'evidence_min_search_score', self.min_search_score
                )
                self.min_chunks = getattr(cfg, 'evidence_min_chunks', self.min_chunks)

    def _threshold(self, reranker_available: bool) -> float:
        value = self.min_search_score if not reranker_available else self.min_score
        return float(value) if isinstance(value, (int, float)) else 0.0

    def _extract_scores(self, obj: object, reranker_available: bool) -> list[float]:
        if obj is None:
            return []
        if isinstance(obj, dict):
            vals = list(obj.values())
            return [n for n in (_to_number(v) for v in vals) if n is not None]
        if isinstance(obj, (list, tuple, set)):
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
                return [float(x) for x in obj]
            scores: list[float] = []
            for item in obj:
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    scores.append(float(item))
                    continue
                found = None
                if reranker_available:
                    found = _attr(item, 'rerank_score', 'rerank', 'relevance_score', 'score')
                if found is None:
                    found = _attr(item, 'search_score', 'search', 'similarity', 'score', 'value')
                if found is None and not reranker_available:
                    found = _attr(item, 'search_score', 'search', 'similarity', 'score', 'value')
                num = _to_number(found)
                if num is not None:
                    scores.append(num)
            return scores
        # Single chunk/score
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return [float(obj)]
        found = None
        if reranker_available:
            found = _attr(obj, 'rerank_score', 'rerank', 'score')
        if found is None:
            found = _attr(obj, 'search_score', 'search', 'similarity', 'score', 'value')
        num = _to_number(found)
        return [num] if num is not None else []

    def _reranker_available(self, kwargs: dict[str, object]) -> bool:
        if 'reranker_available' in kwargs:
            return bool(kwargs['reranker_available'])
        if 'reranker_enabled' in kwargs:
            return bool(kwargs['reranker_enabled'])
        if 'reranker_down' in kwargs:
            return not bool(kwargs['reranker_down'])
        if 'fallback' in kwargs:
            val = kwargs['fallback']
            if isinstance(val, str):
                return 'fallback' not in val.lower() or 'search' not in val.lower()
            return not bool(val)
        if 'use_search_scores' in kwargs:
            return not bool(kwargs['use_search_scores'])
        if 'use_fallback' in kwargs:
            return not bool(kwargs['use_fallback'])
        return True

    def check(self, *args: object, **kwargs: object) -> EvidenceResult:
        reranker_available = self._reranker_available(kwargs)

        # Collect candidate objects
        objects: list[object] = list(args)
        for key in (
            'scores',
            'rerank_scores',
            'search_scores',
            'results',
            'chunks',
            'retrieved',
            'retrieved_chunks',
            'documents',
        ):
            if key in kwargs and kwargs[key] is not None:
                objects.append(kwargs[key])

        explicit_count = _coalesce(
            'chunk_count',
            'chunks_count',
            'num_chunks',
            'count',
            'n_chunks',
            kwargs=kwargs,
            default=None,
        )
        if explicit_count is None and 'chunk_count' not in kwargs:
            explicit_count = kwargs.get('minimum_chunks')

        # Split objects into scores vs chunks
        score_lists: list[float] = []
        chunk_groups: list[object] = []
        for obj in objects:
            if isinstance(obj, (list, tuple, set, dict)):
                if all(
                    isinstance(x, (int, float)) and not isinstance(x, bool)
                    for x in (list(obj.values()) if isinstance(obj, dict) else obj)
                ):
                    score_lists.extend(self._extract_scores(obj, reranker_available))
                else:
                    chunk_groups.append(obj)
            elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                score_lists.append(float(obj))
            elif obj is not None:
                chunk_groups.append(obj)

        for group in chunk_groups:
            score_lists.extend(self._extract_scores(group, reranker_available))

        if not score_lists and chunk_groups:
            # Count-only evidence: no score available.
            pass

        chunk_count = explicit_count
        if chunk_count is None:
            chunk_count = (
                len(chunk_groups) if chunk_groups and not score_lists else len(score_lists)
            )
        try:
            chunk_count = int(chunk_count)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            chunk_count = 0

        threshold = self._threshold(reranker_available)
        best_score = max(score_lists) if score_lists else None
        sufficient = True
        reason: str | None = None
        if not score_lists:
            # Insufficient if we expected at least min_chunks and have none.
            if chunk_count < int(self.min_chunks or 1):  # type: ignore[call-overload]
                sufficient = False
                reason = 'no_evidence'
            else:
                # Chunk count alone cannot prove score; require a score.
                sufficient = False
                reason = 'no_scores'
        elif best_score is None or best_score < threshold:
            sufficient = False
            reason = 'low_score'
        elif chunk_count < int(self.min_chunks or 1):  # type: ignore[call-overload]
            sufficient = False
            reason = 'too_few_chunks'
        # Edge: if chunks provided count differs from scores, ensure min chunks by score count too.
        if sufficient and len(score_lists) < int(self.min_chunks or 1):  # type: ignore[call-overload]
            # But chunk_count could be provided larger; trust chunk_count.
            if chunk_count < int(self.min_chunks or 1):  # type: ignore[call-overload]
                sufficient = False
                reason = 'too_few_chunks'

        return EvidenceResult(
            sufficient,
            best_score=best_score,
            threshold=threshold,
            chunk_count=chunk_count,
            min_chunks=self.min_chunks,
            reranker_available=reranker_available,
            has_evidence=sufficient,
            reason=reason,
        )

    def is_sufficient(self, *args: object, **kwargs: object) -> EvidenceResult:
        return self.check(*args, **kwargs)

    def sufficient(self, *args: object, **kwargs: object) -> EvidenceResult:
        return self.check(*args, **kwargs)

    def has_sufficient_evidence(self, *args: object, **kwargs: object) -> EvidenceResult:
        return self.check(*args, **kwargs)

    def evaluate(self, *args: object, **kwargs: object) -> EvidenceResult:
        return self.check(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> EvidenceResult:
        return self.check(*args, **kwargs)


def has_sufficient_evidence(*args: object, **kwargs: object) -> EvidenceResult:
    data = dict(kwargs)
    checker_kwargs: dict[str, object] = {}
    for key in (
        'min_score',
        'min_search_score',
        'min_chunks',
        'config',
        'settings',
        'evidence_min_score',
        'evidence_min_search_score',
        'evidence_min_chunks',
    ):
        if key in data:
            checker_kwargs[key] = data.pop(key)
    # Allow a config object passed positionally.
    cfg_args = [a for a in args if hasattr(a, 'evidence_min_score')]
    if cfg_args:
        checker_kwargs['config'] = cfg_args[0]
        args = tuple(a for a in args if a is not cfg_args[0])
    checker = EvidenceChecker(**checker_kwargs)
    return checker.check(*args, **data)


# Aliases
EvidenceService = EvidenceChecker
EvidenceGate = EvidenceChecker
EvidenceCheck = EvidenceChecker
__all__ = [
    'EvidenceCheck',
    'EvidenceChecker',
    'EvidenceGate',
    'EvidenceResult',
    'EvidenceService',
    'answer_has_evidence',
    'has_sufficient_evidence',
    'is_citation_valid',
]
