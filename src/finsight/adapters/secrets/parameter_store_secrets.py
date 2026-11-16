"""Parameter Store secrets adapter (pilot).

Retrieves secrets from AWS Systems Manager Parameter Store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.secrets_provider import SecretsProvider

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mypy_boto3_ssm.client import SSMClient  # type: ignore[import-not-found]


class ParameterStoreSecrets(SecretsProvider):
    """Secrets provider using AWS Systems Manager Parameter Store."""

    def __init__(self, client: Any, **kwargs: Any) -> None:
        """Initialize the Parameter Store secrets adapter.

        Args:
            client: Pre-configured boto3 SSM client (required).
            **kwargs: Additional arguments (unused, for compatibility).
        """
        self._client: SSMClient = client

    async def get_secret(self, name: str) -> str | None:
        """Get a secret value by name from Parameter Store.

        Args:
            name: The parameter name to retrieve.

        Returns:
            The parameter value as a string, or None if not found.
        """
        try:
            response = self._client.get_parameter(Name=name, WithDecryption=True)
            return response['Parameter']['Value']  # type: ignore[no-any-return]
        except self._client.exceptions.ParameterNotFound:
            return None

    async def get_secrets(self, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name from Parameter Store.

        Uses GetParameters for batch retrieval (max 10 parameters per call).

        Args:
            names: A sequence of parameter names to retrieve.

        Returns:
            A dictionary mapping parameter names to their values (or None if not found).
        """
        if not names:
            return {}

        result: dict[str, str | None] = {}
        # Parameter Store GetParameters supports max 10 parameters per call
        for i in range(0, len(names), 10):
            batch = names[i : i + 10]
            response = self._client.get_parameters(Names=batch, WithDecryption=True)

            # Map found parameters
            for param in response.get('Parameters', []):
                result[param['Name']] = param['Value']

            # Mark missing parameters as None
            for name in batch:
                if name not in result:
                    result[name] = None

        return result


__all__ = ['ParameterStoreSecrets']
