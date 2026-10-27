"""Postgres/Aurora user repository implementing the UserRepository port."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from finsight.core.types import CompanyId, Role, UserId
from finsight.domain.entities.user import User
from finsight.domain.ports.user_repository import UserRepository as UserRepositoryPort

from .base_repository import BaseRepository


_TABLE = 'users'


def _row_to_user(row: Any) -> User | None:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        user_id = mapping['id']
        company_id = mapping['company_id']
        email = mapping['email']
        role = mapping['role']
        created_at = mapping.get('created_at') if hasattr(mapping, 'get') else mapping['created_at']
        updated_at = mapping.get('updated_at') if hasattr(mapping, 'get') else mapping['updated_at']
    else:
        user_id, company_id, email, role, created_at, updated_at = row[:6]
    return User(
        id=UserId(str(user_id)),
        company_id=CompanyId(str(company_id)),
        email=str(email),
        role=Role(str(role)),
        created_at=created_at if isinstance(created_at, (datetime, type(None))) else None,
        updated_at=updated_at if isinstance(updated_at, (datetime, type(None))) else None,
    )


class UserRepository(UserRepositoryPort, BaseRepository):
    """Concrete user repository with RLS context enforcement."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)

    async def create_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
        email: str,
        role: Role,
    ) -> User:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            INSERT INTO {_TABLE} (id, company_id, email, role)
            VALUES (:id, :company_id, :email, :role)
            ON CONFLICT (company_id, email) DO UPDATE
                SET role = EXCLUDED.role, updated_at = now()
            RETURNING id, company_id, email, role, created_at, updated_at
            """,
            {
                'id': str(user_id),
                'company_id': str(company_id),
                'email': email,
                'role': str(role),
            },
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        user = _row_to_user(row)
        if user is None:
            return User(id=user_id, company_id=company_id, email=email, role=role)
        return user

    async def get_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> User | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT id, company_id, email, role, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id AND id = :id
            """,
            {'company_id': str(company_id), 'id': str(user_id)},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_user(row)

    async def get_user_by_email(
        self,
        company_id: CompanyId,
        email: str,
    ) -> User | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT id, company_id, email, role, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id AND email = :email
            """,
            {'company_id': str(company_id), 'email': email},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_user(row)

    async def list_users(
        self,
        company_id: CompanyId,
    ) -> list[User]:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT id, company_id, email, role, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            """,
            {'company_id': str(company_id)},
        )
        rows = result.fetchall() if hasattr(result, 'fetchall') else list(result) if result is not None else []
        users: list[User] = []
        for row in rows:
            user = _row_to_user(row)
            if user is not None:
                users.append(user)
        return users

    async def update_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
        email: str | None = None,
        role: Role | None = None,
    ) -> User | None:
        await self._set_rls_context(company_id)
        row = None
        try:
            result = await self._execute(
                f"""
                UPDATE {_TABLE}
                SET email = COALESCE(:email, email),
                    role = COALESCE(:role, role),
                    updated_at = now()
                WHERE company_id = :company_id AND id = :id
                RETURNING id, company_id, email, role, created_at, updated_at
                """,
                {
                    'company_id': str(company_id),
                    'id': str(user_id),
                    'email': email,
                    'role': (str(role) if role is not None else None),
                },
            )
            row = result.fetchone() if hasattr(result, 'fetchone') else None
        except Exception:
            return None
        return _row_to_user(row)

    async def delete_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> bool:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND id = :id',
            {'company_id': str(company_id), 'id': str(user_id)},
        )
        rowcount = getattr(result, 'rowcount', None)
        if rowcount is None:
            return True
        return bool(rowcount)


PostgresUserRepository = UserRepository
UserRepositoryAdapter = PostgresUserRepository
PostgresUserRepo = PostgresUserRepository
RLSUserRepository = UserRepository
UserRepo = PostgresUserRepository

__all__ = [
    'PostgresUserRepository',
    'UserRepository',
    'UserRepositoryAdapter',
    'PostgresUserRepo',
    'RLSUserRepository',
    'UserRepo',
]
