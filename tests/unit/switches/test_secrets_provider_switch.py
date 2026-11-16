"""Tests for the secrets_provider config switch.

Both paths (parameter_store pilot, secrets_manager standard) must be tested.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finsight.core.config.models import SwitchesConfig


class TestSecretsProviderSwitch:
    """Test that the secrets_provider switch works correctly."""

    def test_secrets_provider_parameter_store_on(self) -> None:
        """Test parameter_store (pilot) path is selectable."""
        config = SwitchesConfig(secrets_provider='parameter_store')  # pragma: allowlist secret
        assert config.secrets_provider == 'parameter_store'  # pragma: allowlist secret

    def test_secrets_provider_secrets_manager_off(self) -> None:
        """Test secrets_manager (standard) path is selectable."""
        config = SwitchesConfig(secrets_provider='secrets_manager')  # pragma: allowlist secret
        assert config.secrets_provider == 'secrets_manager'  # pragma: allowlist secret

    def test_secrets_provider_invalid_fails(self) -> None:
        """Test that invalid secrets_provider values fail validation."""
        with pytest.raises(ValidationError):
            SwitchesConfig(secrets_provider='invalid_provider')  # pragma: allowlist secret
