"""Port for user data access."""

from __future__ import annotations

from abc import ABC, abstractmethod

from finsight.core.types import CompanyId, Role, UserId
from finsight.domain.entities.user import User


class UserRepository(ABC):
    """Interface for storing and retrieving users."""

    @abstractmethod
    async def create_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
        email: str,
        role: Role,
    ) -> User:
        """Create a user record. Returns the created user."""
        raise NotImplementedError

    @abstractmethod
    async def get_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> User | None:
        """Get a user by id within the tenant scope."""
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(
        self,
        company_id: CompanyId,
        email: str,
    ) -> User | None:
        """Get a user by email within the tenant scope."""
        raise NotImplementedError

    @abstractmethod
    async def list_users(
        self,
        company_id: CompanyId,
    ) -> list[User]:
        """List users within the tenant scope."""
        raise NotImplementedError

    @abstractmethod
    async def update_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
        email: str | None = None,
        role: Role | None = None,
    ) -> User | None:
        """Update a user. Returns the updated user (or None)."""
        raise NotImplementedError

    @abstractmethod
    async def delete_user(
        self,
        company_id: CompanyId,
        user_id: UserId,
    ) -> bool:
        """Delete a user record. Returns True if deleted."""
        raise NotImplementedError
