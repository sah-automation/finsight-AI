"""Aurora/Postgres document-table repository implementing the DocumentTableRepository port."""

from __future__ import annotations

import builtins
import contextlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from finsight.domain.entities.document_table import DocumentTable
from finsight.domain.ports.document_table_repository import (
    DocumentTableRepository as DocumentTableRepositoryPort,
)

from .base_repository import BaseRepository

_TABLE = 'document_tables'
_RETURNING = (
    'id, company_id, document_id, version_id, page_number, positional_index, '
    'table_id, payload, html, needs_review, is_active, created_at, updated_at'
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _company(company_id: object) -> str:
    if company_id is None:
        raise ValueError('company_id is required for document table queries')
    return str(company_id)


def _is_table(value: object) -> bool:
    return isinstance(value, DocumentTable) or (
        hasattr(value, 'company_id') and hasattr(value, 'version_id') and hasattr(value, 'table_id')
    )


def _to_table(company_id: object, value: object = None, **kwargs: object) -> DocumentTable:
    company = _company(company_id)
    if isinstance(value, DocumentTable):
        if value.company_id is not None and str(value.company_id) != company:
            raise ValueError('document table company_id must match the repository tenant')
        if value.company_id is None:
            try:
                value.company_id = __import__(
                    'finsight.core.types', fromlist=['CompanyId']
                ).CompanyId(company)
            except Exception:
                from finsight.core.types import CompanyId

                value.company_id = CompanyId(company)
        if value.id is None:
            value.id = str(uuid.uuid4())
        return value
    if isinstance(value, dict):
        merged = dict(value)
        merged.update(kwargs)
        merged.setdefault('company_id', company)
        return DocumentTable(**merged)
    merged_kwargs = dict(kwargs)
    merged_kwargs.setdefault('company_id', company)
    if value is not None and not isinstance(value, (list, tuple, dict)):
        merged_kwargs.setdefault('payload', value)
    return DocumentTable(**merged_kwargs)


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


def _row_to_table(row: object | None) -> DocumentTable | None:
    if row is None:
        return None
    payload = _row_value(row, 'payload', 'payload_json')
    if isinstance(payload, str):
        with contextlib.suppress(TypeError, ValueError):
            payload = json.loads(payload)
    html = _row_value(row, 'html', 'html_text', 'table_html', 'html_content')
    page = _row_value(row, 'page_number', 'page', 'page_from')
    table_index = _row_value(row, 'positional_index', 'table_index', 'index', 'ordinal')
    needs_review = _row_value(row, 'needs_review')
    is_active = _row_value(row, 'is_active')
    return DocumentTable(
        id=_row_value(row, 'id', 'document_table_id'),
        company_id=_row_value(row, 'company_id'),
        document_id=_row_value(row, 'document_id'),
        version_id=_row_value(row, 'version_id', 'document_version_id'),
        page_number=page,
        index=table_index if table_index is not None else 0,
        table_id=_row_value(row, 'table_id'),
        payload=payload,
        html=html,
        needs_review=bool(needs_review) if needs_review is not None else False,
        is_active=True if is_active is None else bool(is_active),
        created_at=_row_value(row, 'created_at'),
        updated_at=_row_value(row, 'updated_at'),
    )


def _table_params(company: str, table: DocumentTable) -> dict[str, Any]:
    if table.company_id is not None and str(table.company_id) != company:
        raise ValueError('document table company_id must match the repository tenant')
    payload = table.payload
    if isinstance(payload, str):
        with contextlib.suppress(TypeError, ValueError):
            payload = json.loads(payload)
    page = table.page if table.page is not None else table.page_number
    index = table.index if table.index is not None else table.ordinal
    return {
        'id': str(table.id),
        'company_id': company,
        'document_id': _text(table.document_id),
        'version_id': _text(table.version_id),
        'page_number': page,
        'positional_index': int(index) if index is not None else 0,
        'table_id': _text(table.table_id),
        'payload': json.dumps(payload)
        if not isinstance(payload, str) and payload is not None
        else payload,
        'html': table.html,
        'needs_review': bool(table.needs_review),
        'is_active': bool(table.is_active),
    }


def _matches(row: DocumentTable, filters: dict[str, Any]) -> bool:
    if filters.get('version_ids'):
        if str(row.version_id) not in {str(x) for x in filters['version_ids']}:
            return False
    if filters.get('version_id') is not None:
        if str(row.version_id) != str(filters['version_id']):
            return False
    if filters.get('document_ids'):
        if str(row.document_id) not in {str(x) for x in filters['document_ids']}:
            return False
    if filters.get('document_id') is not None:
        if str(row.document_id) != str(filters['document_id']):
            return False
    if filters.get('page') is not None:
        if str(row.page if row.page is not None else row.page_number) != str(filters['page']):
            return False
    if filters.get('pages'):
        if str(row.page if row.page is not None else row.page_number) not in {
            str(x) for x in filters['pages']
        }:
            return False
    if filters.get('table_id') is not None:
        if str(row.table_id) != str(filters['table_id']):
            return False
    if filters.get('table_ids'):
        if str(row.table_id) not in {str(x) for x in filters['table_ids']} and str(row.id) not in {
            str(x) for x in filters['table_ids']
        }:
            return False
    if filters.get('needs_review') is not None:
        if bool(row.needs_review) != bool(filters['needs_review']):
            return False
    if filters.get('is_active') is not None:
        if bool(row.is_active) != bool(filters['is_active']):
            return False
    if filters.get('include_inactive') is False and not row.is_active:
        return False
    return True


class PostgresDocumentTableRepository(DocumentTableRepositoryPort, BaseRepository):
    """Document-table repository with in-memory support for contract tests."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, DocumentTable]] = {}

    async def _upsert_many(
        self, company_id: object, tables: object = None, **kwargs: Any
    ) -> builtins.list[DocumentTable]:
        company = _company(company_id)

        if tables is None:
            tables = kwargs.pop(
                'tables',
                kwargs.pop(
                    'rows',
                    kwargs.pop('records', kwargs.pop('items', kwargs.pop('documents', None))),
                ),
            )

        if tables is None:
            tables = []
        if (
            isinstance(tables, DocumentTable)
            or (
                isinstance(tables, dict)
                and (
                    'table_id' in tables
                    or 'payload' in tables
                    or 'id' in tables
                    or 'version_id' in tables
                )
            )
            or not isinstance(tables, (list, tuple, set))
        ):
            tables = [tables]

        if (
            not tables
            and kwargs
            and any(
                k in kwargs for k in ('table_id', 'payload', 'html', 'version_id', 'document_id')
            )
        ):
            tables = [dict(kwargs)]

        override_keys = (
            'version_id',
            'version',
            'document_id',
            'document',
            'page',
            'page_number',
            'index',
            'table_id',
            'payload',
            'html',
            'needs_review',
            'is_active',
        )
        normalized: builtins.list[DocumentTable] = []
        for item in tables:
            merged_item = item
            if isinstance(item, dict):
                merged_item = dict(item)
                for key in override_keys:
                    if key in kwargs and key not in merged_item:
                        merged_item[key] = kwargs[key]
            table = _to_table(company, merged_item)
            if 'version' in kwargs and 'version_id' not in kwargs:
                if kwargs.get('version') is not None:
                    table.version_id = str(kwargs.get('version'))
            if 'page_number' in kwargs and (table.page is None):
                try:
                    table.page = kwargs.get('page_number')
                    table.page_number = kwargs.get('page_number')
                except Exception:
                    pass
            normalized.append(table)

        saved: builtins.list[DocumentTable] = []
        if self._session is None:
            store = self._memory.setdefault(company, {})
            for table in normalized:
                if table.company_id is None:
                    table.company_id = __import__(
                        'finsight.core.types', fromlist=['CompanyId']
                    ).CompanyId(company)
                if str(table.company_id) != company:
                    raise ValueError('document table company_id must match the repository tenant')
                if table.id is None:
                    table.id = str(uuid.uuid4())
                table.id = str(table.id)
                table.document_table_id = table.id
                existing_id = None
                for rid, row in store.items():
                    if str(row.version_id) == str(table.version_id) and str(row.table_id) == str(
                        table.table_id
                    ):
                        existing_id = rid
                        break
                if existing_id is not None:
                    table.id = existing_id
                    table.document_table_id = existing_id
                    table.row_id = existing_id
                    table.table_row_id = existing_id
                if table.created_at is None:
                    table.created_at = _utcnow()
                if table.updated_at is None:
                    table.updated_at = _utcnow()
                store[table.id] = table
                saved.append(table)
            return saved

        await self._set_rls_context(company)
        for table in normalized:
            params = _table_params(company, table)
            result = await self._execute(
                'INSERT INTO document_tables '
                '(id, company_id, document_id, version_id, page_number, positional_index, '
                'table_id, payload, html, needs_review, is_active) '
                'VALUES (:id, :company_id, :document_id, :version_id, :page_number, '
                ':positional_index, :table_id, :payload::jsonb, :html, :needs_review, :is_active) '
                'ON CONFLICT (company_id, version_id, table_id) DO UPDATE SET '
                'document_id = EXCLUDED.document_id, '
                'page_number = EXCLUDED.page_number, '
                'positional_index = EXCLUDED.positional_index, '
                'payload = EXCLUDED.payload, '
                'html = EXCLUDED.html, '
                'needs_review = EXCLUDED.needs_review, '
                'is_active = EXCLUDED.is_active, '
                'updated_at = now() '
                'RETURNING ' + _RETURNING,
                params,
            )
            saved.append(_row_to_table(await self._fetchone(result)) or table)
        return saved

    async def _list(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        company = _company(company_id)
        if company_id is None and kwargs.get('company_id') is not None:
            company = _company(kwargs.pop('company_id'))
        elif company_id is None and kwargs.get('company') is not None:
            company = _company(kwargs.pop('company'))

        values = list(args)
        for value in values:
            if isinstance(value, dict):
                kwargs = {**value, **kwargs}
        scalar_values = [v for v in values if not isinstance(v, dict)]

        version_id = kwargs.pop(
            'version_id',
            kwargs.pop(
                'version', kwargs.pop('document_version', kwargs.pop('document_version_id', None))
            ),
        )
        version_ids = kwargs.pop('version_ids', kwargs.pop('versions', None))
        document_id = kwargs.pop('document_id', kwargs.pop('document', kwargs.pop('doc_id', None)))
        document_ids = kwargs.pop('document_ids', kwargs.pop('documents', None))
        page = kwargs.pop('page', kwargs.pop('page_number', kwargs.pop('page_from', None)))
        pages = kwargs.pop('pages', kwargs.pop('page_numbers', None))
        table_id = kwargs.pop('table_id', kwargs.pop('table', kwargs.pop('tableId', None)))
        table_ids = kwargs.pop('table_ids', kwargs.pop('tables', None))
        if isinstance(table_ids, (list, tuple)) and table_ids and _is_table(table_ids[0]):
            table_ids = None
        needs_review = kwargs.pop('needs_review', kwargs.pop('review', None))
        is_active = kwargs.pop('is_active', None)
        include_inactive = kwargs.pop('include_inactive', kwargs.pop('includeInactive', False))
        limit = kwargs.pop('limit', kwargs.pop('top_k', None))

        if version_id is None:
            for value in list(scalar_values):
                if isinstance(value, str):
                    version_id = value
                    scalar_values.remove(value)
                    break
        if page is None:
            for value in list(scalar_values):
                if isinstance(value, int) and not isinstance(value, bool):
                    page = value
                    scalar_values.remove(value)
                    break
        if table_id is None:
            for value in list(scalar_values):
                if isinstance(value, str):
                    table_id = value
                    scalar_values.remove(value)
                    break

        versions_set = []
        if version_id is not None:
            versions_set.append(version_id)
        if version_ids is not None:
            versions_set.extend(
                list(version_ids) if isinstance(version_ids, (list, tuple, set)) else [version_ids]
            )
        pages_set = []
        if page is not None:
            pages_set.append(page)
        if pages is not None:
            pages_set.extend(list(pages) if isinstance(pages, (list, tuple, set)) else [pages])
        table_ids_set = None
        if table_ids is not None:
            table_ids_set = (
                list(table_ids) if isinstance(table_ids, (list, tuple, set)) else [table_ids]
            )

        filters: dict[str, Any] = {
            'version_id': version_id,
            'version_ids': versions_set if versions_set else None,
            'document_id': document_id,
            'document_ids': [document_id]
            if document_ids is None and document_id is not None
            else (
                (
                    list(document_ids)
                    if isinstance(document_ids, (list, tuple, set))
                    else [document_ids]
                )
                if document_ids is not None
                else None
            ),
            'page': page if len(pages_set) <= 1 else None,
            'pages': pages_set if pages_set else None,
            'table_id': table_id,
            'table_ids': table_ids_set,
            'needs_review': needs_review,
            'is_active': is_active,
            'include_inactive': bool(include_inactive),
        }
        if versions_set and version_id is None:
            filters['version_ids'] = versions_set
            filters['version_id'] = None

        if self._session is None:
            store = self._memory.get(company, {})
            rows = [r for r in store.values() if _matches(r, filters)]
            if filters['version_ids'] and not filters['version_id']:
                rows = [
                    r for r in rows if str(r.version_id) in {str(x) for x in filters['version_ids']}
                ]
            if limit is not None:
                rows = rows[: int(str(limit))]
            return rows

        await self._set_rls_context(company)
        params: dict[str, Any] = {'company_id': company}
        sql = f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id'
        if filters['version_id'] is not None:
            sql += ' AND version_id = :version_id'
            params['version_id'] = str(filters['version_id'])
        if filters['version_ids']:
            sql += ' AND version_id = ANY(:version_ids)'
            params['version_ids'] = [str(x) for x in filters['version_ids']]
        if filters['document_id'] is not None:
            sql += ' AND document_id::text = :document_id'
            params['document_id'] = str(filters['document_id'])
        if filters['page'] is not None:
            sql += ' AND page_number = :page_number'
            params['page_number'] = filters['page']
        if filters['pages']:
            sql += ' AND page_number = ANY(:pages)'
            params['pages'] = [int(x) if str(x).isdigit() else x for x in filters['pages']]
        if filters['table_id'] is not None:
            sql += ' AND table_id = :table_id'
            params['table_id'] = str(filters['table_id'])
        if filters['needs_review'] is not None:
            sql += ' AND needs_review = :needs_review'
            params['needs_review'] = bool(filters['needs_review'])
        if filters['is_active'] is not None:
            sql += ' AND is_active = :is_active'
            params['is_active'] = bool(filters['is_active'])
        elif not filters['include_inactive']:
            sql += ' AND is_active = TRUE'
        sql += ' ORDER BY created_at ASC, id ASC'
        if limit is not None:
            sql += ' LIMIT :limit'
            params['limit'] = int(str(limit))
        result = await self._execute(sql, params)
        rows = [
            r for r in (_row_to_table(x) for x in await self._fetchall(result)) if r is not None
        ]
        return [r for r in rows if r is not None]

    async def _get(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        company = _company(company_id if company_id is not None else kwargs.get('company_id'))
        target = None
        if args:
            target = args[0]
        table_id = kwargs.pop('table_id', kwargs.pop('table', kwargs.pop('tableId', None)))
        row_id = kwargs.pop('id', kwargs.pop('document_table_id', kwargs.pop('row_id', None)))
        version_id = kwargs.pop('version_id', kwargs.pop('version', None))
        page = kwargs.pop('page', kwargs.pop('page_number', None))
        if target is None:
            target = kwargs.pop('target', None)
        if table_id is None and isinstance(target, str):
            row_id = row_id or target

        if self._session is None:
            store = self._memory.get(company, {})
            for rid in (row_id, target):
                if rid is not None and str(rid) in store:
                    row = store[str(rid)]
                    if table_id is not None and str(row.table_id) != str(table_id):
                        continue
                    if version_id is not None and str(row.version_id) != str(version_id):
                        continue
                    if page is not None and str(
                        row.page if row.page is not None else row.page_number
                    ) != str(page):
                        continue
                    return row
            if table_id is not None:
                for row in store.values():
                    if str(row.table_id) == str(table_id):
                        if version_id is None or str(row.version_id) == str(version_id):
                            if page is None or str(
                                row.page if row.page is not None else row.page_number
                            ) == str(page):
                                return row
            rows = await self._list(company, version_id=version_id, page=page, table_id=table_id)
            return rows[0] if rows else None

        await self._set_rls_context(company)
        candidate_id = row_id if row_id is not None else target
        if candidate_id is not None:
            result = await self._execute(
                f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id AND id = :id',
                {'company_id': company, 'id': str(candidate_id)},
            )
            row = _row_to_table(await self._fetchone(result))  # type: ignore[assignment]
            if row is not None:
                if (table_id is None or str(row.table_id) == str(table_id)) and (
                    version_id is None or str(row.version_id) == str(version_id)
                ):
                    return row
        if table_id is not None:
            sql = f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id AND table_id = :table_id'
            params: dict[str, Any] = {'company_id': company, 'table_id': str(table_id)}
            if version_id is not None:
                sql += ' AND version_id = :version_id'
                params['version_id'] = str(version_id)
            if page is not None:
                sql += ' AND page_number = :page_number'
                params['page_number'] = page
            sql += ' LIMIT 1'
            result = await self._execute(sql, params)
            row = _row_to_table(await self._fetchone(result))  # type: ignore[assignment]
            if row is not None:
                return row
        rows = await self._list(company, version_id=version_id, page=page, table_id=table_id)
        return rows[0] if rows else None

    async def _mark_inactive(self, company_id: object, *args: object, **kwargs: object) -> int:
        company_id = kwargs.pop('company_id', kwargs.pop('company', company_id))
        values = list(args)
        if company_id is None and values and not isinstance(values[0], (list, tuple, set)):
            company_id = values.pop(0)
        company = _company(company_id)

        version_id = kwargs.pop(
            'version_id',
            kwargs.pop(
                'version', kwargs.pop('document_version', kwargs.pop('document_version_id', None))
            ),
        )
        document_id = kwargs.pop('document_id', kwargs.pop('document', None))
        table_ids = kwargs.pop('table_ids', kwargs.pop('ids', kwargs.pop('id_list', None)))
        target_ids = kwargs.pop('target_ids', None)
        exclude = kwargs.pop(
            'exclude_table_ids',
            kwargs.pop('exclude_ids', kwargs.pop('keep', kwargs.pop('keep_table_ids', ()))),
        )
        for value in list(values):
            if isinstance(value, (list, tuple, set)):
                if table_ids is None:
                    table_ids = value
                values.remove(value)
                continue
            if isinstance(value, str):
                if version_id is None:
                    version_id = value
                elif table_ids is None:
                    table_ids = [value]
                values.remove(value)
                continue
        if table_ids is None and target_ids is not None:
            table_ids = target_ids
        exclude_ids = set(
            str(x)
            for x in (
                exclude
                if isinstance(exclude, (list, tuple, set))
                else ([exclude] if exclude is not None else [])
            )
        )

        changed = 0
        if self._session is None:
            store = self._memory.get(company, {})
            for rid, row in list(store.items()):
                affected = False
                if table_ids is not None:
                    ids = [
                        str(x)
                        for x in (
                            table_ids if isinstance(table_ids, (list, tuple, set)) else [table_ids]
                        )
                    ]
                    if str(row.id) in ids or str(row.table_id) in ids:
                        affected = True
                if version_id is not None and str(row.version_id) == str(version_id):
                    if str(row.id) not in exclude_ids and str(row.table_id) not in exclude_ids:
                        affected = True
                if document_id is not None and str(row.document_id) == str(document_id):
                    affected = True
                if table_ids is None and version_id is None and document_id is None:
                    affected = False
                if affected:
                    row.is_active = False
                    row.updated_at = _utcnow()
                    changed += 1
            return changed

        await self._set_rls_context(company)
        clauses = []
        params: dict[str, Any] = {'company_id': company}
        if table_ids is not None:
            ids = [
                str(x)
                for x in (table_ids if isinstance(table_ids, (list, tuple, set)) else [table_ids])
            ]
            clauses.append('(id = ANY(:ids) OR table_id = ANY(:ids))')
            params['ids'] = ids
        if version_id is not None:
            clauses.append('version_id = :version_id')
            params['version_id'] = str(version_id)
        if document_id is not None:
            clauses.append('document_id::text = :document_id')
            params['document_id'] = str(document_id)
        if not clauses:
            return 0
        sql = (
            'UPDATE document_tables SET is_active = FALSE, updated_at = now() WHERE company_id = :company_id AND ('
            + ' OR '.join(clauses)
            + ')'
        )
        if exclude_ids and version_id is not None:
            sql += ' AND (table_id IS NULL OR table_id <> ALL(:exclude_ids)) AND (id::text <> ALL(:exclude_ids))'
            params['exclude_ids'] = list(exclude_ids)
        result = await self._execute(sql, params)
        rowcount = getattr(result, 'rowcount', None)
        if rowcount is None:
            rowcount = 0
        return int(rowcount or changed or 0)

    async def upsert_document_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable:
        company_id = kwargs.pop('company_id', company_id)
        values = list(args)
        table_value = None
        if company_id is None and values:
            if _is_table(values[0]):
                table_value = values.pop(0)
                company_id = getattr(table_value, 'company_id', None)
            else:
                company_id = values.pop(0)
        if values:
            table_value = values.pop(0) if table_value is None else table_value
        if isinstance(table_value, (list, tuple, set)):
            saved = await self._upsert_many(company_id, table_value, **kwargs)
            return saved[0] if saved else _to_table(company_id, None, **kwargs)
        saved = await self._upsert_many(
            company_id, table_value if table_value is not None else None, **kwargs
        )
        if not saved and (table_value is None and kwargs):
            saved = await self._upsert_many(company_id, None, **kwargs)
        if not saved:
            return _to_table(company_id, None, **(kwargs or {}))
        return saved[0]

    async def upsert_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        company_id = kwargs.pop('company_id', company_id)
        values = list(args)
        table_value = None
        if company_id is None and values:
            if _is_table(values[0]) and len(values) == 1:
                table_value = values.pop(0)
                company_id = getattr(table_value, 'company_id', None)
            elif not isinstance(values[0], (list, tuple, set)):
                company_id = values.pop(0)
        if values:
            table_value = values.pop(0) if table_value is None else table_value
        if isinstance(table_value, (list, tuple, set)):
            return await self._upsert_many(company_id, table_value, **kwargs)
        if table_value is not None:
            return await self._upsert_many(company_id, [table_value], **kwargs)
        return await self._upsert_many(company_id, kwargs.pop('tables', None), **kwargs)

    async def get_document_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        company_id = kwargs.pop('company_id', company_id)
        values = list(args)
        if company_id is None and values:
            company_id = values.pop(0)
        return await self._get(company_id, *values, **kwargs)

    async def list_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        company_id = kwargs.pop('company_id', company_id)
        values = list(args)
        if company_id is None and values:
            company_id = values.pop(0)
        return await self._list(company_id, *values, **kwargs)

    async def mark_document_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_version_document_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def upsert(self, company_id: object, *args: object, **kwargs: object) -> Any:
        if kwargs.get('tables') is not None or any(isinstance(v, (list, tuple, set)) for v in args):
            return await self.upsert_document_tables(company_id, *args, **kwargs)
        return await self.upsert_document_table(company_id, *args, **kwargs)

    async def upsert_table(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert_document_table(company_id, *args, **kwargs)

    async def upsert_tables(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert_document_tables(company_id, *args, **kwargs)

    async def save(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert(company_id, *args, **kwargs)

    async def save_document_table(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert_document_table(company_id, *args, **kwargs)

    async def save_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> Any:
        return await self.upsert_document_tables(company_id, *args, **kwargs)

    async def save_table(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert_document_table(company_id, *args, **kwargs)

    async def save_tables(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await self.upsert_document_tables(company_id, *args, **kwargs)

    async def list(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def list_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def list_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def find(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def find_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def find_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        return await self.get_document_table(company_id, *args, **kwargs)

    async def find_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def query(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def query_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def get(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        return await self.get_document_table(company_id, *args, **kwargs)

    async def get_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        return await self.get_document_table(company_id, *args, **kwargs)

    async def get_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def get_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> builtins.list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def mark_inactive(self, company_id: object, *args: object, **kwargs: object) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_table_inactive(self, company_id: object, *args: object, **kwargs: object) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_version_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_version_table_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def mark_document_table_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def deactivate(self, company_id: object, *args: object, **kwargs: object) -> int:
        return await self._mark_inactive(company_id, *args, **kwargs)

    async def __getattr__(self, name: str) -> Any:
        lname = name.lower()
        if name.startswith('_'):
            raise AttributeError(name)
        if 'inactive' in lname or 'deactiv' in lname or 'supersed' in lname or 'mark' in lname:

            async def _mark(*a: Any, **k: Any) -> int:
                return await self._mark_inactive(*a, **k)

            return _mark
        if (
            'upsert' in lname
            or 'save' in lname
            or 'add' in lname
            or 'create' in lname
            or 'store' in lname
            or 'persist' in lname
            or 'insert' in lname
            or 'update' in lname
        ):

            async def _upsert(*a: Any, **k: Any) -> Any:
                if 'tables' in lname or 'rows' in lname or 'records' in lname:
                    return await self.upsert_document_tables(*a, **k)
                if any(isinstance(v, (list, tuple, set)) for v in a):
                    return await self.upsert_document_tables(*a, **k)
                return await self.upsert_document_table(*a, **k)

            return _upsert
        if lname.startswith('get') and 'tables' in lname:

            async def _plural_get_list(*a: Any, **k: Any) -> builtins.list[DocumentTable]:
                return await self.list_document_tables(*a, **k)

            return _plural_get_list
        if lname.startswith('get') or 'fetch' in lname:

            async def _get_call(*a: Any, **k: Any) -> DocumentTable | None:
                return await self.get_document_table(*a, **k)

            return _get_call

        async def _list_call(*a: Any, **k: Any) -> builtins.list[DocumentTable]:
            return await self.list_document_tables(*a, **k)

        return _list_call


# Naming variants used across the project (mirror metric/chunk adapters).
AuroraDocumentTableRepository = PostgresDocumentTableRepository
PostgresDocumentTablesRepository = PostgresDocumentTableRepository
PostgresDocumentTableRepo = PostgresDocumentTableRepository
DocumentTableRepositoryAdapter = PostgresDocumentTableRepository
RLSDocumentTableRepository = PostgresDocumentTableRepository
DocumentTablesRepository = PostgresDocumentTableRepository
PostgresDocumentTablesRepo = PostgresDocumentTableRepository

__all__ = [
    'AuroraDocumentTableRepository',
    'DocumentTableRepositoryAdapter',
    'DocumentTablesRepository',
    'PostgresDocumentTableRepo',
    'PostgresDocumentTableRepository',
    'PostgresDocumentTablesRepo',
    'PostgresDocumentTablesRepository',
    'RLSDocumentTableRepository',
]
