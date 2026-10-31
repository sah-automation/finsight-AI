"""Compatibility dispatch for document-table repository method aliases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _getattr(self: PostgresDocumentTableRepository, name: str) -> Any:
    lname = name.lower()
    if name.startswith('_'):
        raise AttributeError(name)
    if 'inactive' in lname or 'deactiv' in lname or 'supersed' in lname or 'mark' in lname:

        async def _mark(*a: Any, **k: Any) -> Any:
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

        async def _plural_get_list(*a: Any, **k: Any) -> Any:
            return await self.list_document_tables(*a, **k)

        return _plural_get_list
    if lname.startswith('get') or 'fetch' in lname:

        async def _get_call(*a: Any, **k: Any) -> Any:
            return await self.get_document_table(*a, **k)

        return _get_call

    async def _list_call(*a: Any, **k: Any) -> Any:
        return await self.list_document_tables(*a, **k)

    return _list_call
