"""Port for secrets resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class SecretsProvider(ABC):
    """Interface for retrieving secrets from a provider."""

    @abstractmethod
    async def get_secret(self, name: str) -> str | None:
        """Get a secret value by name.

        Args:
            name: The secret name/key to retrieve.

        Returns:
            The secret value as a string, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_secrets(self, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name.

        Args:
            names: A sequence of secret names/keys to retrieve.

        Returns:
            A dictionary mapping secret names to their values (or None if not found).
        """
        raise NotImplementedError


__all__ = ['SecretsProvider']
