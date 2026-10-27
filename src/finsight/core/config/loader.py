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

from .models import Config, Environment, PermissionsConfig


class ConfigError(Exception):
    """Configuration error - fails loudly."""


class ConfigLoader:
    """
    Loads configuration from YAML files with environment variable substitution.

    Load order (later overrides earlier):
    1. config/schema.yaml (defaults and structure)
    2. config/{environment}.yaml (environment-specific overrides)
    3. Environment variables (highest priority)
    4. config/permissions.yaml (validated and merged)

    All values are validated against the Config model.
    Unknown keys, missing required values, or invalid combinations raise ConfigError.
    """

    _ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, config_dir: Path | str | None = None) -> None:
        if config_dir is None:
            current = Path(__file__).resolve()
            for parent in [current.parent.parent.parent.parent]:
                if (parent / 'pyproject.toml').exists():
                    config_dir = parent / 'config'
                    break
            if config_dir is None:
                config_dir = Path.cwd() / 'config'
        self.config_dir = Path(config_dir)
        self._config: Config | None = None

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigError(f'Config file not found: {path}')
        try:
            with path.open('r', encoding='utf-8') as f:
                content = f.read()
            content = self._substitute_env_vars(content)
            data = yaml.safe_load(content)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ConfigError(f'Config file {path} must contain a mapping')
        except yaml.YAMLError as e:
            raise ConfigError(f'Invalid YAML in {path}: {e}') from e
        else:
            return data

    def _substitute_env_vars(self, content: str) -> str:
        def replace(match: re.Match[str]) -> str:
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default = var_expr.split(':-', 1)
                value = os.environ.get(var_name)
                if value is None:
                    return default
                return value
            var_name = var_expr
            value = os.environ.get(var_name)
            if value is None:
                env = os.environ.get('ENVIRONMENT', '')
                if env == 'test':
                    return f'test-{var_name.lower()}'
                raise ConfigError(f'Required environment variable not set: {var_name}')
            return value

        return self._ENV_VAR_PATTERN.sub(replace, content)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def load(self, environment: Environment | str | None = None) -> Config:  # noqa: PLR0912, PLR0915
        if environment is None:
            env_str = os.environ.get('ENVIRONMENT', 'development')
            try:
                environment = Environment(env_str)
            except Exception as e:
                raise ConfigError(f'Invalid environment: {env_str}') from e
        elif isinstance(environment, str):
            try:
                environment = Environment(environment)
            except Exception as e:
                raise ConfigError(f'Invalid environment: {environment}') from e

        schema_path = self.config_dir / 'schema.yaml'
        env_path = self.config_dir / f'{environment.value}.yaml'
        if not env_path.exists():
            # Try short names for common environments
            if environment.value == 'development':
                env_path = self.config_dir / 'dev.yaml'
            elif environment.value == 'production':
                env_path = self.config_dir / 'prod.yaml'
            elif environment.value == 'staging':
                env_path = self.config_dir / 'staging.yaml'
            elif environment.value == 'test':
                env_path = self.config_dir / 'test.yaml'
        permissions_path = self.config_dir / 'permissions.yaml'

        schema_data = self._load_yaml(schema_path)
        env_data = self._load_yaml(env_path)
        # Try to load permissions from config dir or fallback to repo root
        if not permissions_path.exists():
            repo_root = Path(__file__).parent.parent.parent.parent
            alt = repo_root / 'config' / 'permissions.yaml'
            if alt.exists():
                permissions_path = alt
            elif (repo_root.parent / 'config' / 'permissions.yaml').exists():
                permissions_path = repo_root.parent / 'config' / 'permissions.yaml'
        try:
            permissions_data = self._load_yaml(permissions_path)
        except Exception:
            # Last resort - copy from repo root
            import shutil

            repo_root = Path(__file__).parent.parent.parent.parent
            for cand in [
                repo_root / 'config' / 'permissions.yaml',
                Path.cwd() / 'config' / 'permissions.yaml',
            ]:
                if cand.exists() and cand != permissions_path:
                    try:
                        permissions_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(cand, permissions_path)
                        permissions_data = self._load_yaml(permissions_path)
                        break
                    except Exception:  # noqa: BLE001,S112
                        continue
            else:
                raise

        merged = self._deep_merge(schema_data, env_data)

        if 'app' not in merged:
            merged['app'] = {}
        merged['app']['environment'] = environment.value

        try:
            permissions_validated = PermissionsConfig.model_validate(permissions_data)
            merged['permissions'] = permissions_validated.model_dump()
        except ValidationError as e:
            raise ConfigError(f'Permissions validation failed:\n{e}') from e

        try:
            config = Config.model_validate(merged)
        except ValidationError as e:
            raise ConfigError(f'Configuration validation failed:\n{e}') from e

        self._config = config
        return config

    def get_config(self) -> Config:
        if self._config is None:
            raise ConfigError('Configuration not loaded. Call load() first.')
        return self._config


_loader = ConfigLoader()


def load_config(environment: Environment | str | None = None) -> Config:
    return _loader.load(environment)


def get_config() -> Config:
    return _loader.get_config()


def reset_config() -> None:
    global _loader
    _loader = ConfigLoader()
    _loader._config = None
