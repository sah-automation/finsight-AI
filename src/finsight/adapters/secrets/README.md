# Secrets Adapters

This directory contains adapters for the `SecretsProvider` port.

## Adapters

- **ParameterStoreSecrets** (pilot) - Retrieves secrets from AWS Systems Manager Parameter Store
- **SecretsManagerSecrets** (standard) - Retrieves secrets from AWS Secrets Manager

## Configuration

The active adapter is selected via the `secrets_provider` switch in `SwitchesConfig`:

- `parameter_store` - Uses ParameterStoreSecrets (pilot)
- `secrets_manager` - Uses SecretsManagerSecrets (standard)

## Contract Tests

Both adapters must pass the same contract test suite in `tests/contract/secrets/`.

## Resolution

The adapter is resolved in `core/config/_resolve_config.py` via `resolve_secrets_provider()`.
This is the only place in the codebase that directly instantiates AWS clients.
