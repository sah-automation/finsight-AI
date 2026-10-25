# Config Loader - Reads, merges, validates configuration
# ONLY this module reads config files and environment variables.
# Fails loudly on any error - no silent fallbacks.

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import Config, Environment


class ConfigError(Exception):
    """Configuration error - fails loudly."""


class ConfigLoader:
    """
    Loads configuration from YAML files with environment variable substitution.

    Load order (later overrides earlier):
    1. config/schema.yaml (defaults and structure)
    2. config/{environment}.yaml (environment-specific overrides)
    3. Environment variables (highest priority)

    All values are validated against the Config model.
    Unknown keys, missing required values, or invalid combinations raise ConfigError.
    """

    _ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, config_dir: Path | str | None = None) -> None:
        self.config_dir = (
            Path(config_dir)
            if config_dir
            else Path(__file__).parent.parent.parent.parent.parent / 'config'
        )
        self._schema_path = self.config_dir / 'schema.yaml'
        self._env_file_map = {
            Environment.DEVELOPMENT: 'dev.yaml',
            Environment.TEST: 'test.yaml',
            Environment.STAGING: 'staging.yaml',
            Environment.PRODUCTION: 'prod.yaml',
        }

    def load(self, environment: Environment | str | None = None) -> Config:
        """
        Load and validate configuration for the given environment.

        Args:
            environment: Target environment. If None, reads from ENVIRONMENT env var
                        or defaults to development.

        Returns:
            Validated, frozen Config object.

        Raises:
            ConfigError: If any validation fails, file missing, or unknown keys found.
        """
        # Determine environment
        if environment is None:
            environment = os.getenv('ENVIRONMENT', 'development')
        if isinstance(environment, str):
            try:
                environment = Environment(environment.lower())
            except ValueError as e:
                raise ConfigError(
                    f'Invalid environment: {environment}. '
                    f'Must be one of: {[e.value for e in Environment]}'
                ) from e

        # Load and merge configs
        merged = self._load_and_merge(environment)

        # Substitute environment variables
        merged = self._substitute_env_vars(merged)

        # Validate against Pydantic model
        try:
            config = Config(**merged)
        except ValidationError as e:
            errors = self._format_validation_errors(e)
            raise ConfigError(f'Configuration validation failed:\n{errors}') from e

        # Log active configuration (sanitized)
        self._log_config(config, environment)

        return config

    def _load_and_merge(self, environment: Environment) -> dict[str, Any]:
        """Load schema and environment overlay, merge them."""
        # Load schema (base defaults)
        if not self._schema_path.exists():
            raise ConfigError(f'Schema file not found: {self._schema_path}')

        with self._schema_path.open() as f:
            schema = yaml.safe_load(f) or {}

        # Load environment-specific config
        env_file = self._env_file_map.get(environment)
        if not env_file:
            raise ConfigError(f'No config file mapped for environment: {environment}')

        env_path = self.config_dir / env_file
        if not env_path.exists():
            raise ConfigError(f'Environment config not found: {env_path}')

        with env_path.open() as f:
            env_config = yaml.safe_load(f) or {}

        # Deep merge
        return self._deep_merge(schema, env_config)

    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute ${VAR_NAME} with environment variable values."""
        if isinstance(data, str):
            match = self._ENV_VAR_PATTERN.fullmatch(data.strip())
            if match:
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    raise ConfigError(
                        f'Required environment variable not set: {var_name}. '
                        f'Referenced in config value: {data}'
                    )
                return value

            # Also handle partial substitution in strings
            def replace_var(m: re.Match[str]) -> str:
                var_name = m.group(1)
                value = os.getenv(var_name)
                if value is None:
                    raise ConfigError(
                        f'Required environment variable not set: {var_name}. '
                        f'Referenced in config: {data}'
                    )
                return value

            return self._ENV_VAR_PATTERN.sub(replace_var, data)

        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}

        if isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]

        return data

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries. Override takes precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _format_validation_errors(self, error: ValidationError) -> str:
        """Format Pydantic validation errors for readability."""
        lines = []
        for err in error.errors():
            loc = ' -> '.join(str(x) for x in err['loc'])
            msg = err['msg']
            typ = err['type']
            lines.append(f'  {loc}: {msg} ({typ})')
        return '\n'.join(lines)

    def _log_config(self, config: Config, environment: Environment) -> None:
        """Log active configuration (sanitized - no secrets)."""
        # Import here to avoid circular imports
        from finsight.core.logging import get_logger

        logger = get_logger(__name__)

        # Sanitize sensitive fields
        sanitized = config.model_dump()
        self._sanitize_dict(sanitized)

        logger.info(
            'Configuration loaded',
            extra={
                'environment': environment.value,
                'config': sanitized,
            },
        )

    def _sanitize_dict(self, data: dict[str, Any], path: str = '') -> None:
        """Recursively remove sensitive values from dict for logging."""
        sensitive_keys = {
            'password',
            'secret',
            'key',
            'token',
            'credential',
            'access_key',
            'secret_key',
            'api_key',
            'private_key',
        }

        for key, value in list(data.items()):
            current_path = f'{path}.{key}' if path else key
            key_lower = key.lower()

            if any(sensitive in key_lower for sensitive in sensitive_keys):
                data[key] = '***REDACTED***'
            elif isinstance(value, dict):
                self._sanitize_dict(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._sanitize_dict(item, f'{current_path}[{i}]')


# ============================================================
# Singleton accessor (used by composition root)
# ============================================================

_config_instance: Config | None = None


def get_config() -> Config:
    """Get the loaded configuration singleton. Must call load_config() first."""
    global _config_instance
    if _config_instance is None:
        raise ConfigError('Configuration not loaded. Call load_config() at application startup.')
    return _config_instance


def load_config(
    environment: Environment | str | None = None, config_dir: Path | str | None = None
) -> Config:
    """Load configuration at application startup. Call once."""
    global _config_instance
    loader = ConfigLoader(config_dir)
    _config_instance = loader.load(environment)
    return _config_instance


def reset_config() -> None:
    """Reset configuration singleton. For testing only."""
    global _config_instance
    _config_instance = None
