"""Aurora/pgvector hybrid search adapter.

The adapter runs vector similarity and Postgres full-text search in one query,
fuses the two scores with the configured weights and applies the tenant,
access-scope, active-chunk and lifecycle filters before returning candidates.
Every statement names ``company_id`` first so the partitioned table is pruned to
one company partition, and RLS is set as a second lock.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.hybrid_search import HybridSearch as HybridSearchPort

from ._aurora_pg_vector_search_shared import (
    _as_list,
    _config_value,
    _first,
    _float,
    _resolve_config,
    _text,
)
from .base_vector_store import BaseVectorStore

if TYPE_CHECKING:
    from .search_result import SearchResult


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

    async def index_chunks(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_search_index_chunks import _index_chunks as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def add_chunk(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_search_add_chunk import _add_chunk as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def clear(self, company_id: Any, *args: Any, **kwargs: Any) -> None:
        from ._aurora_pg_vector_search_clear import _clear as _adapter_method

        await _adapter_method(self, company_id, *args, **kwargs)

    async def search(self, company_id: Any, *args: Any, **kwargs: Any) -> list[SearchResult]:
        from ._aurora_pg_vector_search_search import _search as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

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

    def _record(self, company_id: Any, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        from ._aurora_pg_vector_search__record import _record as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

    def _search_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> list[SearchResult]:
        from ._aurora_pg_vector_search__search_memory import _search_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

    async def _search_sql(self, company_id: Any, *args: Any, **kwargs: Any) -> list[SearchResult]:
        from ._aurora_pg_vector_search__search_sql import _search_sql as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    def _sql(self, company_id: Any, *args: Any, **kwargs: Any) -> str:
        from ._aurora_pg_vector_search__sql import _sql as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

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
