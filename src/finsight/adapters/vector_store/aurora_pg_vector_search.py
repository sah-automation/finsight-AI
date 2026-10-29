"""Aurora/pgvector hybrid search adapter.

The adapter runs vector similarity and Postgres full-text search in one query,
fuses the two scores with the configured weights and applies the tenant,
access-scope, active-chunk and lifecycle filters before returning candidates.
Every statement names ``company_id`` first so the partitioned table is pruned to
one company partition, and RLS is set as a second lock.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from typing import Any

from finsight.domain.ports.hybrid_search import HybridSearch as HybridSearchPort

from .base_vector_store import BaseVectorStore
from .search_result import SearchResult

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


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in ('retrieval', 'search', 'vector_store'):
                nested = config.get(section)
                if isinstance(nested, dict) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in ('retrieval', 'search', 'vector_store'):
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
        if any(hasattr(arg, attr) for attr in ('retrieval', 'switches', 'app', 'vector_store')):
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
        raise ValueError('company_id is required for hybrid search')
    return value


def _as_list(value: object) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _keyword_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(text)) / len(query_tokens)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(float(a) ** 2 for a in left))
    right_norm = math.sqrt(sum(float(b) ** 2 for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _row_value(row: object, *names: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _metadata(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_to_result(row: object) -> SearchResult:
    text = _text(_row_value(row, 'content', 'text', 'chunk_text'))
    metadata = _metadata(_row_value(row, 'metadata'))
    return SearchResult(
        chunk_id=_text(_row_value(row, 'chunk_id', 'id')),
        company_id=_text(_row_value(row, 'company_id')),
        document_id=_text(_row_value(row, 'document_id')),
        version_id=_text(_row_value(row, 'version_id', 'document_version')),
        text=text,
        content=text,
        context_header=_text(_row_value(row, 'context_header')),
        page_number=_row_value(row, 'page_number', 'page_from'),
        category=_text(_row_value(row, 'category')),
        is_active=bool(_row_value(row, 'is_active')),
        metadata=metadata,
        score=_float(_row_value(row, 'score', 'fused_score')),
        vector_score=_float(_row_value(row, 'vector_score', 'similarity')),
        keyword_score=_float(_row_value(row, 'keyword_score')),
    )


class AuroraPgVectorSearch(HybridSearchPort, BaseVectorStore):
    """Hybrid vector and Postgres full-text search for one company."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self.config = kwargs.get('config') or _resolve_config(**kwargs)
        self.vector_weight = _float(
            _first(
                kwargs,
                'vector_weight',
                default=_config_value(self.config, 'vector_weight', default=0.7),
            ),
            0.7,
        )
        self.keyword_weight = _float(
            _first(
                kwargs,
                'keyword_weight',
                default=_config_value(self.config, 'keyword_weight', default=0.3),
            ),
            0.3,
        )
        self.top_k = int(
            _first(kwargs, 'top_k', default=_config_value(self.config, 'top_k', default=50)) or 50
        )
        self.hybrid_search_enabled = bool(
            _first(
                kwargs,
                'hybrid_search_enabled',
                default=_config_value(self.config, 'hybrid_search_enabled', default=True),
            )
        )
        self._chunks: dict[str, dict[str, dict[str, Any]]] = {}

    async def index_chunks(
        self,
        company_id: object,
        chunks: Sequence[object],
        *,
        vectors: object = None,
        categories: object = None,
        **kwargs: object,
    ) -> int:
        """Seed the in-memory store used when no database session is wired."""
        company = _company(company_id)
        vector_values = _as_list(vectors)
        category_values = _as_list(categories)
        stored = self._chunks.setdefault(company, {})
        written = 0
        for index, chunk in enumerate(chunks):
            record = self._record(company, chunk, index, vector_values, category_values)
            if record is None:
                continue
            stored[record['chunk_id']] = record
            written += 1
        return written

    async def add_chunk(
        self, company_id: object, chunk: object, *, vector: object = None, **kwargs: object
    ) -> int:
        return await self.index_chunks(
            company_id,
            [chunk],
            vectors=[vector] if vector is not None else None,
            categories=kwargs.get('category'),
        )

    async def clear(self, company_id: object) -> None:
        self._chunks.pop(_company(company_id), None)

    async def search(
        self, company_id: object, *args: object, **kwargs: object
    ) -> list[SearchResult]:
        company = _company(company_id)
        values: dict[str, Any] = dict(kwargs)
        query, embedding = self._parse_args(args, values)
        access_scope = self._scope(values)
        document_ids = [
            _text(item) for item in _as_list(_first(values, 'document_ids', 'documents'))
        ]
        version_ids = [_text(item) for item in _as_list(_first(values, 'version_ids', 'versions'))]
        top_k = int(_first(values, 'top_k', 'limit', default=self.top_k) or self.top_k)
        vector_weight = _float(_first(values, 'vector_weight', default=self.vector_weight))
        keyword_weight = _float(_first(values, 'keyword_weight', default=self.keyword_weight))
        include_inactive = bool(_first(values, 'include_inactive', default=False))
        hybrid = bool(_first(values, 'hybrid_search_enabled', default=self.hybrid_search_enabled))
        if not hybrid:
            keyword_weight = 0.0
        if self._session is None:
            return self._search_memory(
                company,
                query,
                embedding,
                access_scope,
                document_ids,
                version_ids,
                top_k,
                vector_weight,
                keyword_weight,
                include_inactive,
            )
        return await self._search_sql(
            company,
            query,
            embedding,
            access_scope,
            document_ids,
            version_ids,
            top_k,
            vector_weight,
            keyword_weight,
            include_inactive,
            values,
        )

    @staticmethod
    def _parse_args(args: tuple[object, ...], values: dict[str, Any]) -> tuple[str, list[float]]:
        query = _text(_first(values, 'query', 'question', 'text'))
        embedding = _as_list(_first(values, 'embedding', 'query_embedding', 'vector'))
        for arg in args:
            if isinstance(arg, str) and not query:
                query = arg
            elif isinstance(arg, dict):
                values.update(arg)
            elif isinstance(arg, Iterable) and not isinstance(arg, (str, bytes)):
                embedding = list(arg)
        return query, [float(value) for value in embedding]

    @staticmethod
    def _scope(values: dict[str, Any]) -> list[str] | None:
        raw = _first(values, 'access_scope', 'scope', 'allowed_categories')
        categories = _first(values, 'categories', 'category')
        if raw is None and categories is None:
            return None
        allowed = {_text(item) for item in _as_list(raw)} if raw is not None else None
        requested = (
            {_text(item) for item in _as_list(categories)} if categories is not None else None
        )
        if allowed is None:
            return sorted(requested or [])
        if requested is not None:
            return sorted(allowed & requested)
        return sorted(allowed)

    def _record(
        self, company: str, chunk: object, index: int, vectors: list[Any], categories: list[Any]
    ) -> dict[str, Any] | None:
        chunk_company = _text(_row_value(chunk, 'company_id'))
        if chunk_company and chunk_company != company:
            return None
        if bool(_row_value(chunk, 'is_parent')):
            return None
        chunk_id = _text(_row_value(chunk, 'chunk_id', 'id'))
        if not chunk_id:
            return None
        vector = vectors[index] if index < len(vectors) else None
        category = (
            _text(categories[index])
            if index < len(categories)
            else _text(_row_value(chunk, 'category'))
        )
        return {
            'chunk_id': chunk_id,
            'company_id': company,
            'document_id': _text(_row_value(chunk, 'document_id')),
            'version_id': _text(_row_value(chunk, 'version_id', 'document_version')),
            'text': _text(_row_value(chunk, 'text', 'content', 'chunk_text')),
            'context_header': _text(_row_value(chunk, 'context_header')),
            'page_number': _row_value(chunk, 'page_number', 'page_from'),
            'category': category,
            'is_active': True
            if _row_value(chunk, 'is_active') is None
            else bool(_row_value(chunk, 'is_active')),
            'metadata': _metadata(_row_value(chunk, 'metadata')),
            'vector': [float(value) for value in _as_list(vector)],
        }

    def _search_memory(  # noqa: PLR0913, PLR0917 - filter inputs are explicit
        self,
        company: str,
        query: str,
        embedding: list[float],
        access_scope: list[str] | None,
        document_ids: list[str],
        version_ids: list[str],
        top_k: int,
        vector_weight: float,
        keyword_weight: float,
        include_inactive: bool,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for record in self._chunks.get(company, {}).values():
            if not include_inactive and not record['is_active']:
                continue
            if access_scope is not None and record['category'] not in access_scope:
                continue
            if document_ids and record['document_id'] not in document_ids:
                continue
            if version_ids and record['version_id'] not in version_ids:
                continue
            vector_score = _cosine(embedding, record['vector'])
            keyword_score = _keyword_score(query, record['text'])
            score = vector_weight * vector_score + keyword_weight * keyword_score
            results.append(
                SearchResult(
                    chunk_id=record['chunk_id'],
                    company_id=company,
                    document_id=record['document_id'],
                    version_id=record['version_id'],
                    text=record['text'],
                    content=record['text'],
                    context_header=record['context_header'],
                    page_number=record['page_number'],
                    category=record['category'],
                    is_active=record['is_active'],
                    metadata=dict(record['metadata']),
                    score=score,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                )
            )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[: max(1, top_k)]

    async def _search_sql(  # noqa: PLR0913, PLR0917 - filter inputs are explicit
        self,
        company: str,
        query: str,
        embedding: list[float],
        access_scope: list[str] | None,
        document_ids: list[str],
        version_ids: list[str],
        top_k: int,
        vector_weight: float,
        keyword_weight: float,
        include_inactive: bool,
        values: dict[str, Any],
    ) -> list[SearchResult]:
        await self._execute(
            "SELECT set_config('app.company_id', :company_id, true)", {'company_id': company}
        )
        params: dict[str, Any] = {'company_id': company, 'top_k': max(1, top_k)}
        sql = self._sql(
            query,
            embedding,
            access_scope,
            document_ids,
            version_ids,
            vector_weight,
            keyword_weight,
            include_inactive,
            values,
            params,
        )
        result = await self._execute(sql, params)
        return [_row_to_result(row) for row in await self._fetchall(result)]

    def _sql(  # noqa: PLR0913, PLR0917 - SQL inputs are explicit
        self,
        query: str,
        embedding: list[float],
        access_scope: list[str] | None,
        document_ids: list[str],
        version_ids: list[str],
        vector_weight: float,
        keyword_weight: float,
        include_inactive: bool,
        values: dict[str, Any],
        params: dict[str, Any],
    ) -> str:
        vector_expr = '0.0'
        if embedding:
            params['embedding'] = json.dumps(embedding)
            vector_expr = '1 - (c.embedding <=> CAST(:embedding AS vector))'
        keyword_expr = '0.0'
        if query and keyword_weight > 0.0:
            params['query'] = query
            keyword_expr = (
                "ts_rank_cd(to_tsvector('english', coalesce(c.content, '')), "
                "plainto_tsquery('english', :query))"
            )
        score_expr = f'({vector_weight} * ({vector_expr}) + {keyword_weight} * ({keyword_expr}))'
        filters = [
            'c.company_id = :company_id',
            'c.is_parent = FALSE',
            'd.deleted_at IS NULL',
        ]
        if not include_inactive:
            filters.append('c.is_active = TRUE')
        filters.extend(self._filter_sql(access_scope, document_ids, version_ids, values, params))
        return (
            'SELECT c.chunk_id, c.company_id, c.document_id, c.version_id, c.content, '
            'c.context_header, c.page_number, c.metadata, c.is_active, d.category, '
            f'{vector_expr} AS vector_score, {keyword_expr} AS keyword_score, '
            f'{score_expr} AS score '
            'FROM document_chunks c '
            'JOIN documents d ON d.company_id = c.company_id AND d.id = c.document_id '
            f'WHERE {" AND ".join(filters)} '
            'ORDER BY score DESC, c.chunk_id ASC LIMIT :top_k'
        )

    @staticmethod
    def _filter_sql(
        access_scope: list[str] | None,
        document_ids: list[str],
        version_ids: list[str],
        values: dict[str, Any],
        params: dict[str, Any],
    ) -> list[str]:
        filters: list[str] = []
        if access_scope is not None:
            if not access_scope:
                filters.append('FALSE')
            else:
                filters.append('d.category = ANY(:access_scope)')
                params['access_scope'] = access_scope
        if document_ids:
            filters.append('c.document_id = ANY(:document_ids)')
            params['document_ids'] = document_ids
        if version_ids:
            filters.append('c.version_id = ANY(:version_ids)')
            params['version_ids'] = version_ids
        period = _first(values, 'period', 'fiscal_period')
        if period is not None:
            filters.append('d.period = :period')
            params['period'] = _text(period)
        return filters


__all__ = ['AuroraPgVectorSearch']
