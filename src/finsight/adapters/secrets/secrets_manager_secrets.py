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

    def _prefix_name(self, company_id: str, name: str) -> str:
        """Prefix the secret name with company_id for multi-tenancy isolation."""
        return f'{company_id}/{name}'

    async def get_secret(self, company_id: str, name: str) -> str | None:
        """Get a secret value by name from Secrets Manager for a specific company.

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            name: The secret name to retrieve.

        Returns:
            The secret value as a string, or None if not found.
        """
        prefixed_name = self._prefix_name(company_id, name)
        try:
            response = self._client.get_secret_value(SecretId=prefixed_name)
            return response['SecretString']  # type: ignore[no-any-return]
        except self._client.exceptions.ResourceNotFoundException:
            return None

    async def get_secrets(self, company_id: str, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name from Secrets Manager for a specific company.

        Secrets Manager doesn't have a batch get operation, so we call GetSecretValue
        for each name sequentially.

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            names: A sequence of secret names to retrieve.

        Returns:
            A dictionary mapping secret names to their values (or None if not found).
        """
        result: dict[str, str | None] = {}
        for name in names:
            result[name] = await self.get_secret(company_id, name)
        return result


__all__ = ['SecretsManagerSecrets']
