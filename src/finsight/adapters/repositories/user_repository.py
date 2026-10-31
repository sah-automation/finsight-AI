"""Postgres/Aurora user repository implementing the UserRepository port."""

from __future__ import annotations

from datetime import UTC, datetime
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
        self._memory: dict[str, dict[str, User]] = {}

    async def create_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
        email: str,
        role: Role,
    ) -> User:
        if self._session is None:
            now = datetime.now(UTC)
            store = self._memory.setdefault(str(company_id), {})
            for existing_id, existing_user in list(store.items()):
                if existing_user.email == email and existing_id != str(user_id):
                    del store[existing_id]
            prior = store.get(str(user_id))
            user = User(
                id=user_id,
                company_id=company_id,
                email=email,
                role=role,
                created_at=prior.created_at if prior is not None else now,
                updated_at=now,
            )
            store[str(user_id)] = user
            return user
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
        row = await self._fetchone(result)
        user_row: User | None = _row_to_user(row)
        if user_row is None:
            return User(id=user_id, company_id=company_id, email=email, role=role)
        return user_row

    async def get_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> User | None:
        if self._session is None:
            return self._memory.get(str(company_id), {}).get(str(user_id))
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT id, company_id, email, role, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id AND id = :id
            """,
            {'company_id': str(company_id), 'id': str(user_id)},
        )
        row = await self._fetchone(result)
        return _row_to_user(row)

    async def get_user_by_email(
        self,
        company_id: CompanyId,
        email: str,
    ) -> User | None:
        if self._session is None:
            for user in self._memory.get(str(company_id), {}).values():
                if user.email == email:
                    return user
            return None
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT id, company_id, email, role, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id AND email = :email
            """,
            {'company_id': str(company_id), 'email': email},
        )
        row = await self._fetchone(result)
        return _row_to_user(row)

    async def list_users(
        self,
        company_id: CompanyId,
    ) -> list[User]:
        if self._session is None:
            return list(self._memory.get(str(company_id), {}).values())
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
        rows = (
            result.fetchall()
            if hasattr(result, 'fetchall')
            else list(result)
            if result is not None
            else []
        )
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
        if self._session is None:
            store = self._memory.get(str(company_id), {})
            existing = store.get(str(user_id))
            if existing is None:
                return None
            updated = User(
                id=existing.id,
                company_id=existing.company_id,
                email=email if email is not None else existing.email,
                role=role if role is not None else existing.role,
                created_at=existing.created_at,
                updated_at=datetime.now(UTC),
            )
            store[str(user_id)] = updated
            return updated
        await self._set_rls_context(company_id)
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
        row = await self._fetchone(result)
        return _row_to_user(row)

    async def delete_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> bool:
        if self._session is None:
            store = self._memory.get(str(company_id), {})
            existed = str(user_id) in store
            store.pop(str(user_id), None)
            return existed
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
    'PostgresUserRepo',
    'PostgresUserRepository',
    'RLSUserRepository',
    'UserRepo',
    'UserRepository',
    'UserRepositoryAdapter',
]
