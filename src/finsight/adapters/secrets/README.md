# Secrets Adapters

This directory contains adapters for the `SecretsProviderPort` interface.

## Adapters

- **LocalSecretsProvider** (`local_adapter.py`) — Pilot path (`secrets_provider=local`)
  - Reads secrets from local `.env` file (development only)

- **SecretsManagerSecretsProvider** (`secretsmanager_adapter.py`) — Standard path (`secrets_provider=secretsmanager`)
  - Reads secrets from AWS Secrets Manager

## Switch

The active adapter is selected via the `secrets_provider` config switch in `envs.yaml`:

```yaml
secrets_provider: local  # or secretsmanager
```

## Contract Tests

See `tests/contract/secrets/` for the port contract tests that both adapters must satisfy.
