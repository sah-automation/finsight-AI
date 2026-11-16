"""Secrets adapters."""

from .parameter_store_secrets import ParameterStoreSecrets
from .secrets_manager_secrets import SecretsManagerSecrets

__all__ = ['ParameterStoreSecrets', 'SecretsManagerSecrets']
