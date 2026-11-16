"""Secrets Manager secrets adapter (standard).

Retrieves secrets from AWS Secrets Manager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.secrets_provider import SecretsProvider

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mypy_boto3_secretsmanager.client import SecretsManagerClient  # type: ignore[import-not-found]


class SecretsManagerSecrets(SecretsProvider):
    """Secrets provider using AWS Secrets Manager."""

    def __init__(self, client: Any, **kwargs: Any) -> None:
        """Initialize the Secrets Manager secrets adapter.

        Args:
            client: Pre-configured boto3 Secrets Manager client (required).
            **kwargs: Additional arguments (unused, for compatibility).
        """
        self._client: SecretsManagerClient = client

    async def get_secret(self, name: str) -> str | None:
        """Get a secret value by name from Secrets Manager.

        Args:
            name: The secret name to retrieve.

        Returns:
            The secret value as a string, or None if not found.
        """
        try:
            response = self._client.get_secret_value(SecretId=name)
            return response['SecretString']  # type: ignore[no-any-return]
        except self._client.exceptions.ResourceNotFoundException:
            return None

    async def get_secrets(self, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name from Secrets Manager.

        Secrets Manager doesn't have a batch get operation, so we call GetSecretValue
        for each name sequentially.

        Args:
            names: A sequence of secret names to retrieve.

        Returns:
            A dictionary mapping secret names to their values (or None if not found).
        """
        result: dict[str, str | None] = {}
        for name in names:
            result[name] = await self.get_secret(name)
        return result


__all__ = ['SecretsManagerSecrets']
