"""Port for secrets resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class SecretsProvider(ABC):
    """Interface for retrieving secrets from a provider."""

    @abstractmethod
    async def get_secret(self, company_id: str, name: str) -> str | None:
        """Get a secret value by name for a specific company.

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            name: The secret name/key to retrieve.

        Returns:
            The secret value as a string, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_secrets(self, company_id: str, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name for a specific company.

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            names: A sequence of secret names/keys to retrieve.

        Returns:
            A dictionary mapping secret names to their values (or None if not found).
        """
        raise NotImplementedError


__all__ = ['SecretsProvider']
