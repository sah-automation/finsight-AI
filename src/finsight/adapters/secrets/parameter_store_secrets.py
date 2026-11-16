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

    def _prefix_name(self, company_id: str, name: str) -> str:
        """Prefix the secret name with company_id for multi-tenancy isolation."""
        return f'{company_id}/{name}'

    async def get_secret(self, company_id: str, name: str) -> str | None:
        """Get a secret value by name from Parameter Store for a specific company.

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            name: The parameter name to retrieve.

        Returns:
            The parameter value as a string, or None if not found.
        """
        prefixed_name = self._prefix_name(company_id, name)
        try:
            response = self._client.get_parameter(Name=prefixed_name, WithDecryption=True)
            return response['Parameter']['Value']  # type: ignore[no-any-return]
        except self._client.exceptions.ParameterNotFound:
            return None

    async def get_secrets(self, company_id: str, names: Sequence[str]) -> dict[str, str | None]:
        """Get multiple secret values by name from Parameter Store for a specific company.

        Uses GetParameters for batch retrieval (max 10 parameters per call).

        Args:
            company_id: The company identifier for multi-tenancy isolation.
            names: A sequence of parameter names to retrieve.

        Returns:
            A dictionary mapping parameter names to their values (or None if not found).
        """
        if not names:
            return {}

        result: dict[str, str | None] = {}
        prefixed_names = [self._prefix_name(company_id, name) for name in names]
        for batch, orig_batch in self._batches(prefixed_names, names):
            result.update(self._fetch_batch(company_id, batch, orig_batch))

        return result

    def _batches(
        self, prefixed: Sequence[str], original: Sequence[str]
    ) -> list[tuple[Sequence[str], Sequence[str]]]:
        """Split names into batches of 10 (Parameter Store limit)."""
        return [(prefixed[i : i + 10], original[i : i + 10]) for i in range(0, len(prefixed), 10)]

    def _fetch_batch(
        self, company_id: str, prefixed_batch: Sequence[str], orig_batch: Sequence[str]
    ) -> dict[str, str | None]:
        """Fetch a single batch of parameters from Parameter Store."""
        response = self._client.get_parameters(Names=list(prefixed_batch), WithDecryption=True)
        batch_result: dict[str, str | None] = {}

        for param in response.get('Parameters', []):
            original_name = param['Name'].removeprefix(f'{company_id}/')
            batch_result[original_name] = param['Value']

        for name in orig_batch:
            if name not in batch_result:
                batch_result[name] = None

        return batch_result


__all__ = ['ParameterStoreSecrets']
