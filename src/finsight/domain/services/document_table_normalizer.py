"""Normalise raw reader table output into the common document-table shape.

Every document reader returns tables in a slightly different dictionary shape.
The save step must persist one shape regardless of the reader, so this service
is the single place that knows the aliases used across the reader adapters.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.document_table import DocumentTable
from finsight.domain.services.document_table_payload import (
    ACTIVE_KEYS,
    HEADER_KEYS,
    HTML_KEYS,
    PAGE_KEYS,
    READER_INDEX_KEYS,
    REVIEW_KEYS,
    ROW_KEYS,
    TABLE_ID_KEYS,
    as_bool,
    build_metadata,
    column_count,
    first_value,
    iter_tables,
    jsonable,
    normalise_headers,
    normalise_rows,
    render_html,
    resolve_page,
    resolve_table_id,
    unique_table_id,
)


class DocumentTableNormalizer:
    """Convert raw reader tables into :class:`DocumentTable` entities."""

    def normalize(self, *args: Any, **kwargs: Any) -> Any:
        return self._normalize_impl(*args, **kwargs)

    def _normalize_impl(
        self,
        tables: Any = None,
        company_id: Any = None,
        document_id: Any = None,
        version_id: Any = None,
        *,
        page_numbers: Iterable[Any] | None = None,
        needs_review: Any = None,
        is_active: Any = None,
    ) -> list[DocumentTable]:
        company_id = company_id or first_value(tables, 'company_id', 'company', 'tenant_id')
        document_id = document_id or first_value(tables, 'document_id', 'documentId', 'doc_id')
        version_id = version_id or first_value(
            tables,
            'version_id',
            'version',
            'document_version',
            'document_version_id',
        )

        normalised: list[DocumentTable] = []
        used_table_ids: set[str] = set()
        for ordinal, raw in enumerate(iter_tables(tables)):
            table = self.normalize_table(
                raw,
                company_id=company_id,
                document_id=document_id,
                version_id=version_id,
                ordinal=ordinal,
                page_numbers=page_numbers,
                needs_review=needs_review,
                is_active=is_active,
            )
            candidate = str(table.table_id) if table.table_id else f'table-{ordinal + 1}'
            table.table_id = unique_table_id(candidate, used_table_ids)
            if isinstance(table.payload, dict):
                table.payload['table_id'] = table.table_id
            normalised.append(table)
        return normalised

    def normalize_table(self, *args: Any, **kwargs: Any) -> Any:
        return self._normalize_table_impl(*args, **kwargs)

    def _normalize_table_impl(
        self,
        table: Any = None,
        company_id: Any = None,
        document_id: Any = None,
        version_id: Any = None,
        ordinal: int = 0,
        *,
        page_numbers: Iterable[Any] | None = None,
        needs_review: Any = None,
        is_active: Any = None,
    ) -> DocumentTable:
        if isinstance(table, DocumentTable):
            self._fill_context(table, company_id, document_id, version_id)
            return table

        raw = self._raw_mapping(table)
        payload, active = self._payload(
            raw,
            ordinal=ordinal,
            page_numbers=page_numbers,
            needs_review=needs_review,
            is_active=is_active,
        )
        return DocumentTable(
            company_id=company_id,
            document_id=document_id,
            version_id=version_id,
            page=payload['page'],
            index=ordinal,
            table_id=str(payload['table_id']),
            payload=payload,
            html=str(payload['html']),
            needs_review=bool(payload['needs_review']),
            is_active=active,
        )

    def normalize_reader_result(
        self,
        result: Any,
        company_id: Any = None,
        document_id: Any = None,
        version_id: Any = None,
    ) -> list[DocumentTable]:
        return self.normalize(  # type: ignore[no-any-return]
            first_value(result, 'tables', default=[]),
            company_id=company_id,
            document_id=document_id,
            version_id=version_id,
            page_numbers=first_value(result, 'page_numbers', 'pages', default=None),
        )

    def _payload(
        self,
        raw: dict[str, Any],
        *,
        ordinal: int,
        page_numbers: Iterable[Any] | None,
        needs_review: Any,
        is_active: Any,
    ) -> tuple[dict[str, Any], bool]:
        rows = normalise_rows(first_value(raw, *ROW_KEYS))
        headers = normalise_headers(first_value(raw, *HEADER_KEYS))
        page = resolve_page(raw, ordinal, page_numbers)
        table_id = resolve_table_id(raw, ordinal)
        review = self._review_flag(raw, needs_review)
        active = as_bool(
            first_value(raw, *ACTIVE_KEYS),
            default=True if is_active is None else as_bool(is_active, default=True),
        )
        explicit_html = first_value(raw, *HTML_KEYS)
        rendered_html = str(explicit_html) if explicit_html else render_html(headers, rows)
        payload: dict[str, Any] = {
            'table_id': table_id,
            'index': ordinal,
            'page': page,
            'headers': jsonable(headers),
            'rows': jsonable(rows),
            'row_count': len(rows),
            'column_count': column_count(rows, headers),
            'needs_review': review,
            'html': rendered_html,
            'metadata': build_metadata(raw, ordinal),
        }
        return payload, active

    @staticmethod
    def _raw_mapping(table: Any) -> dict[str, Any]:
        if isinstance(table, Mapping):
            return dict(table)
        if table is None:
            return {}
        if isinstance(table, (list, tuple)):
            return {'rows': list(table)}
        names = (*ROW_KEYS, *HEADER_KEYS, *TABLE_ID_KEYS, *READER_INDEX_KEYS, *PAGE_KEYS)
        return {name: getattr(table, name) for name in names if hasattr(table, name)}

    def _review_flag(self, raw: dict[str, Any], override: Any) -> bool:
        if override is not None:
            return as_bool(override)
        return as_bool(first_value(raw, *REVIEW_KEYS), default=False)

    @staticmethod
    def _fill_context(
        table: DocumentTable,
        company_id: Any,
        document_id: Any,
        version_id: Any,
    ) -> None:
        if table.company_id is None and company_id is not None:
            table.company_id = CompanyId(str(company_id))
        if table.document_id is None and document_id is not None:
            table.document_id = DocumentId(str(document_id))
            table.document = table.document_id
        if table.version_id is None and version_id is not None:
            table.version_id = str(version_id)
            table.document_version = table.version_id
            table.document_version_id = table.version_id


def normalize_reader_tables(
    result: Any,
    company_id: Any = None,
    document_id: Any = None,
    version_id: Any = None,
) -> list[DocumentTable]:
    """Normalise every table carried by a ReaderResult-like object."""
    return DocumentTableNormalizer().normalize_reader_result(
        result,
        company_id=company_id,
        document_id=document_id,
        version_id=version_id,
    )


__all__ = ['DocumentTableNormalizer', 'normalize_reader_tables']
