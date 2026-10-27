"""Postgres/Aurora company repository implementing the CompanyRepository port."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from finsight.core.types import CompanyId
from finsight.domain.entities.company import Company
from finsight.domain.ports.company_repository import CompanyRepository as CompanyRepositoryPort

from .base_repository import BaseRepository

_TABLE = 'companies'


def _row_to_company(row: Any) -> Company | None:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        company_id = mapping['id']
        name = mapping['name']
        slug = mapping['slug']
        created_at = mapping.get('created_at') if hasattr(mapping, 'get') else mapping['created_at']
        updated_at = mapping.get('updated_at') if hasattr(mapping, 'get') else mapping['updated_at']
    else:
        company_id, name, slug, created_at, updated_at = row[:5]
    return Company(
        id=CompanyId(str(company_id)),
        name=str(name),
        slug=str(slug),
        created_at=created_at if isinstance(created_at, (datetime, type(None))) else None,
        updated_at=updated_at if isinstance(updated_at, (datetime, type(None))) else None,
    )


class CompanyRepository(CompanyRepositoryPort, BaseRepository):
    """Concrete company repository with RLS context enforcement."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._metadata: dict[str, Any] = kwargs

    async def create_company(
        self,
        company_id: CompanyId,
        name: str,
        slug: str,
    ) -> Company:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            INSERT INTO {_TABLE} (id, name, slug)
            VALUES (:id, :name, :slug)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug, updated_at = now()
            RETURNING id, name, slug, created_at, updated_at
            """,
            {'id': str(company_id), 'name': name, 'slug': slug},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        company = _row_to_company(row)
        if company is None:
            return Company(id=company_id, name=name, slug=slug)
        return company

    async def get_company(
        self,
        company_id: CompanyId,
    ) -> Company | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT id, name, slug, created_at, updated_at FROM {_TABLE} WHERE id = :id',
            {'id': str(company_id)},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_company(row)

    async def get_company_by_slug(
        self,
        company_id: CompanyId,
        slug: str,
    ) -> Company | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT id, name, slug, created_at, updated_at FROM {_TABLE} WHERE slug = :slug LIMIT 1',
            {'slug': slug},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_company(row)

    async def update_company(
        self,
        company_id: CompanyId,
        name: str | None = None,
        slug: str | None = None,
    ) -> Company | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            UPDATE {_TABLE}
            SET name = COALESCE(:name, name),
                slug = COALESCE(:slug, slug),
                updated_at = now()
            WHERE id = :id
            RETURNING id, name, slug, created_at, updated_at
            """,
            {'id': str(company_id), 'name': name, 'slug': slug},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_company(row)

    async def delete_company(
        self,
        company_id: CompanyId,
    ) -> bool:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_TABLE} WHERE id = :id',
            {'id': str(company_id)},
        )
        rowcount = getattr(result, 'rowcount', None)
        if rowcount is None:
            return True
        return bool(rowcount)

    async def list_companies(
        self,
        company_id: CompanyId,
    ) -> list[Company]:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT id, name, slug, created_at, updated_at FROM {_TABLE} ORDER BY created_at DESC',
            {},
        )
        rows = result.fetchall() if hasattr(result, 'fetchall') else list(result) if result is not None else []
        companies: list[Company] = []
        for row in rows:
            company = _row_to_company(row)
            if company is not None:
                companies.append(company)
        return companies


# Convenience aliases for varying naming conventions.
PostgresCompanyRepository = CompanyRepository
CompanyRepositoryAdapter = PostgresCompanyRepository
PostgresCompanyRepo = PostgresCompanyRepository
RLSCompanyRepository = CompanyRepository
CompanyRepo = PostgresCompanyRepository

__all__ = [
    'PostgresCompanyRepository',
    'CompanyRepository',
    'CompanyRepositoryAdapter',
    'PostgresCompanyRepo',
    'RLSCompanyRepository',
    'CompanyRepo',
]
