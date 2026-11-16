"""Contract tests for the SecretsProvider port - exercises both ParameterStore and SecretsManager adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from finsight.adapters.secrets.parameter_store_secrets import ParameterStoreSecrets
from finsight.adapters.secrets.secrets_manager_secrets import SecretsManagerSecrets

if TYPE_CHECKING:
    from finsight.domain.ports.secrets_provider import SecretsProvider

pytestmark = pytest.mark.contract


class FakeSSMClient:
    """Fake SSM client for testing ParameterStoreSecrets."""

    def __init__(self) -> None:
        self.parameters: dict[str, str] = {}
        self.exceptions = MagicMock()
        self.exceptions.ParameterNotFound = Exception

    def get_parameter(self, Name: str, WithDecryption: bool = True) -> dict[str, object]:  # noqa: N803
        if Name not in self.parameters:
            raise self.exceptions.ParameterNotFound(f'Parameter {Name} not found')
        return {'Parameter': {'Name': Name, 'Value': self.parameters[Name], 'Type': 'SecureString'}}

    def get_parameters(self, Names: list[str], WithDecryption: bool = True) -> dict[str, object]:  # noqa: N803
        params = []
        for name in Names:
            if name in self.parameters:
                params.append(
                    {'Name': name, 'Value': self.parameters[name], 'Type': 'SecureString'}
                )
        return {
            'Parameters': params,
            'InvalidParameters': [n for n in Names if n not in self.parameters],
        }


class FakeSecretsManagerClient:
    """Fake Secrets Manager client for testing SecretsManagerSecrets."""

    def __init__(self) -> None:
        self.secrets: dict[str, str] = {}
        self.exceptions = MagicMock()
        self.exceptions.ResourceNotFoundException = Exception

    def get_secret_value(self, SecretId: str) -> dict[str, object]:  # noqa: N803
        if SecretId not in self.secrets:
            raise self.exceptions.ResourceNotFoundException(f'Secret {SecretId} not found')
        return {'SecretString': self.secrets[SecretId], 'Name': SecretId}


# Test both adapters
@pytest.fixture(
    params=[ParameterStoreSecrets, SecretsManagerSecrets],
    ids=['parameter_store', 'secrets_manager'],
)
def provider(request: pytest.FixtureRequest) -> SecretsProvider:
    adapter_class = request.param
    if adapter_class is ParameterStoreSecrets:
        fake_client = FakeSSMClient()
        fake_client.parameters = {
            f'{TEST_COMPANY_ID}/test-secret': 'test-value',  # pragma: allowlist secret
            f'{TEST_COMPANY_ID}/db-password': 'super-secret',  # pragma: allowlist secret
            f'{TEST_COMPANY_ID}/api-key': 'abc123',
        }
        return adapter_class(client=fake_client)
    fake_client = FakeSecretsManagerClient()
    fake_client.secrets = {
        f'{TEST_COMPANY_ID}/test-secret': 'test-value',  # pragma: allowlist secret
        f'{TEST_COMPANY_ID}/db-password': 'super-secret',  # pragma: allowlist secret
        f'{TEST_COMPANY_ID}/api-key': 'abc123',
    }
    return adapter_class(client=fake_client)


TEST_COMPANY_ID = 'test-company'


class TestSecretsProviderContract:
    """Contract tests that both ParameterStoreSecrets and SecretsManagerSecrets must pass."""

    async def test_get_secret_existing(self, provider: SecretsProvider) -> None:
        """Test retrieving an existing secret."""
        value = await provider.get_secret(TEST_COMPANY_ID, 'test-secret')
        assert value == 'test-value'

    async def test_get_secret_missing(self, provider: SecretsProvider) -> None:
        """Test retrieving a non-existent secret returns None."""
        value = await provider.get_secret(TEST_COMPANY_ID, 'non-existent')
        assert value is None

    async def test_get_secrets_multiple_existing(self, provider: SecretsProvider) -> None:
        """Test retrieving multiple existing secrets."""
        result = await provider.get_secrets(
            TEST_COMPANY_ID, ['test-secret', 'db-password', 'api-key']
        )
        assert result == {
            'test-secret': 'test-value',  # pragma: allowlist secret
            'db-password': 'super-secret',  # pragma: allowlist secret
            'api-key': 'abc123',
        }

    async def test_get_secrets_mixed_existing_and_missing(self, provider: SecretsProvider) -> None:
        """Test retrieving a mix of existing and missing secrets."""
        result = await provider.get_secrets(
            TEST_COMPANY_ID, ['test-secret', 'non-existent', 'db-password']
        )
        assert result == {
            'test-secret': 'test-value',  # pragma: allowlist secret
            'non-existent': None,
            'db-password': 'super-secret',  # pragma: allowlist secret
        }

    async def test_get_secrets_empty_list(self, provider: SecretsProvider) -> None:
        """Test retrieving an empty list of secrets."""
        result = await provider.get_secrets(TEST_COMPANY_ID, [])
        assert result == {}

    async def test_get_secrets_single_item(self, provider: SecretsProvider) -> None:
        """Test retrieving a single secret via get_secrets."""
        result = await provider.get_secrets(TEST_COMPANY_ID, ['api-key'])
        assert result == {'api-key': 'abc123'}


class TestParameterStoreSecretsSpecific:
    """Tests specific to ParameterStoreSecrets behavior."""

    async def test_batch_retrieval_respects_10_limit(self) -> None:
        """Test that ParameterStore batches requests in groups of 10."""
        fake_client = FakeSSMClient()
        # Create 15 parameters with company prefix
        for i in range(15):
            fake_client.parameters[f'{TEST_COMPANY_ID}/param-{i}'] = f'value-{i}'

        provider = ParameterStoreSecrets(client=fake_client)
        names = [f'param-{i}' for i in range(15)]
        result = await provider.get_secrets(TEST_COMPANY_ID, names)

        assert len(result) == 15
        for i in range(15):
            assert result[f'param-{i}'] == f'value-{i}'

    async def test_with_decryption_true(self) -> None:
        """Test that WithDecryption is set to True by default."""
        fake_client = FakeSSMClient()
        fake_client.parameters[f'{TEST_COMPANY_ID}/encrypted-param'] = 'decrypted-value'

        provider = ParameterStoreSecrets(client=fake_client)
        value = await provider.get_secret(TEST_COMPANY_ID, 'encrypted-param')
        assert value == 'decrypted-value'


class TestSecretsManagerSecretsSpecific:
    """Tests specific to SecretsManagerSecrets behavior."""

    async def test_sequential_retrieval(self) -> None:
        """Test that SecretsManager retrieves secrets sequentially."""
        fake_client = FakeSecretsManagerClient()
        fake_client.secrets = {
            f'{TEST_COMPANY_ID}/secret-1': 'value-1',
            f'{TEST_COMPANY_ID}/secret-2': 'value-2',
        }

        provider = SecretsManagerSecrets(client=fake_client)
        result = await provider.get_secrets(TEST_COMPANY_ID, ['secret-1', 'secret-2'])

        assert result == {'secret-1': 'value-1', 'secret-2': 'value-2'}


# Compatibility tests to ensure both adapters behave consistently
class TestAdapterCompatibility:
    """Tests ensuring both adapters have compatible behavior."""

    async def test_both_return_none_for_missing(self) -> None:
        """Both adapters should return None for missing secrets."""
        ssm_client = FakeSSMClient()
        sm_client = FakeSecretsManagerClient()

        ssm_provider = ParameterStoreSecrets(client=ssm_client)
        sm_provider = SecretsManagerSecrets(client=sm_client)

        assert await ssm_provider.get_secret(TEST_COMPANY_ID, 'missing') is None
        assert await sm_provider.get_secret(TEST_COMPANY_ID, 'missing') is None

    async def test_both_return_dict_for_get_secrets(self) -> None:
        """Both adapters should return a dict from get_secrets."""
        ssm_client = FakeSSMClient()
        ssm_client.parameters[f'{TEST_COMPANY_ID}/key'] = 'value'
        sm_client = FakeSecretsManagerClient()
        sm_client.secrets[f'{TEST_COMPANY_ID}/key'] = 'value'

        ssm_provider = ParameterStoreSecrets(client=ssm_client)
        sm_provider = SecretsManagerSecrets(client=sm_client)

        ssm_result = await ssm_provider.get_secrets(TEST_COMPANY_ID, ['key'])
        sm_result = await sm_provider.get_secrets(TEST_COMPANY_ID, ['key'])

        assert isinstance(ssm_result, dict)
        assert isinstance(sm_result, dict)
        assert ssm_result == sm_result == {'key': 'value'}

    async def test_both_handle_empty_list(self) -> None:
        """Both adapters should handle empty list in get_secrets."""
        ssm_client = FakeSSMClient()
        sm_client = FakeSecretsManagerClient()

        ssm_provider = ParameterStoreSecrets(client=ssm_client)
        sm_provider = SecretsManagerSecrets(client=sm_client)

        assert await ssm_provider.get_secrets(TEST_COMPANY_ID, []) == {}
        assert await sm_provider.get_secrets(TEST_COMPANY_ID, []) == {}
