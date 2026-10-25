# Config Loader Tests

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from finsight.core.config import (
    Config,
    ConfigError,
    ConfigLoader,
    Environment,
    get_config,
    load_config,
    reset_config,
)


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def setup_method(self) -> None:
        reset_config()

    def teardown_method(self) -> None:
        reset_config()

    def test_load_development_config(self) -> None:
        """Test loading development config with defaults."""
        # Set required env vars
        os.environ['VECTOR_DB_HOST'] = 'localhost'
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test-answers'
        os.environ['ROLE_CACHE_TABLE'] = 'test-roles'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/ingestion'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/reprocessing'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/reports'
        os.environ['DLQ_URL'] = 'http://local/dlq'
        os.environ['DOCUMENTS_BUCKET'] = 'test-docs'
        os.environ['REPORTS_BUCKET'] = 'test-reports'
        os.environ['BACKUPS_BUCKET'] = 'test-backups'
        os.environ['COGNITO_USER_POOL_ID'] = 'test-pool'
        os.environ['COGNITO_CLIENT_ID'] = 'test-client'
        os.environ['METERING_TABLE'] = 'test-metering'
        os.environ['OTLP_ENDPOINT'] = 'http://local:4317'

        try:
            config = load_config(Environment.DEVELOPMENT)
            assert isinstance(config, Config)
            assert config.app.environment == Environment.DEVELOPMENT
            assert config.switches.reranker_enabled is True
            assert config.vector_store.host == 'localhost'
        finally:
            # Clean up env vars
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_load_test_config_from_environment_variable(self, monkeypatch) -> None:
        """Test that ENVIRONMENT=test selects config/test.yaml and its local stack values."""
        monkeypatch.setenv('ENVIRONMENT', 'test')

        config = load_config()

        assert config.app.environment == Environment.TEST
        assert config.vector_store.database == 'test'
        assert config.storage.documents_bucket == 'documents'
        assert config.queue.ingestion_queue_url == ('http://localhost:4566/000000000000/ingestion')

    def test_missing_env_var_raises(self, tmp_path) -> None:
        """Test that missing env var raises ConfigError."""
        # Create temp config with env var pattern for host
        config_dir = tmp_path / 'config'
        config_dir.mkdir()

        # Copy schema
        schema = yaml.safe_load(
            (
                Path(__file__).parent.parent.parent.parent.parent / 'config' / 'schema.yaml'
            ).read_text()
        )
        (config_dir / 'schema.yaml').write_text(yaml.dump(schema))

        # Dev config with env var pattern for host (so substitution will fail)
        env_config = {
            'app': {'environment': 'development'},
            'vector_store': {'host': '${VECTOR_DB_HOST}'},
        }
        (config_dir / 'dev.yaml').write_text(yaml.dump(env_config))

        # Set all required env vars EXCEPT VECTOR_DB_HOST
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test'
        os.environ['ROLE_CACHE_TABLE'] = 'test'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/q'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/q'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/q'
        os.environ['DLQ_URL'] = 'http://local/q'
        os.environ['DOCUMENTS_BUCKET'] = 'test'
        os.environ['REPORTS_BUCKET'] = 'test'
        os.environ['BACKUPS_BUCKET'] = 'test'
        os.environ['COGNITO_USER_POOL_ID'] = 'test'
        os.environ['COGNITO_CLIENT_ID'] = 'test'
        os.environ['METERING_TABLE'] = 'test'
        os.environ['OTLP_ENDPOINT'] = 'http://local'

        try:
            loader = ConfigLoader(config_dir)
            with pytest.raises(
                ConfigError, match='Required environment variable not set: VECTOR_DB_HOST'
            ):
                loader.load(Environment.DEVELOPMENT)
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_invalid_environment_raises(self) -> None:
        """Test that invalid environment raises ConfigError."""
        with pytest.raises(ConfigError, match='Invalid environment'):
            load_config('invalid_env')

    def test_unknown_config_key_rejected(self, tmp_path) -> None:
        """Test that unknown keys in config are rejected."""
        # Create a temp config dir with schema + env file with unknown key
        config_dir = tmp_path / 'config'
        config_dir.mkdir()

        # Copy schema (go up 5 levels: tests/unit/core/config -> tests/unit/core -> tests/unit -> tests -> project root)
        schema = yaml.safe_load(
            (
                Path(__file__).parent.parent.parent.parent.parent / 'config' / 'schema.yaml'
            ).read_text()
        )
        (config_dir / 'schema.yaml').write_text(yaml.dump(schema))

        # Create env config with unknown key
        env_config = {
            'app': {'environment': 'development'},
            'unknown_section': {'foo': 'bar'},  # This should be rejected
        }
        (config_dir / 'dev.yaml').write_text(yaml.dump(env_config))

        # Set minimal required env vars
        os.environ['VECTOR_DB_HOST'] = 'localhost'
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test'
        os.environ['ROLE_CACHE_TABLE'] = 'test'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/q'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/q'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/q'
        os.environ['DLQ_URL'] = 'http://local/q'
        os.environ['DOCUMENTS_BUCKET'] = 'test'
        os.environ['REPORTS_BUCKET'] = 'test'
        os.environ['BACKUPS_BUCKET'] = 'test'
        os.environ['COGNITO_USER_POOL_ID'] = 'test'
        os.environ['COGNITO_CLIENT_ID'] = 'test'
        os.environ['METERING_TABLE'] = 'test'
        os.environ['OTLP_ENDPOINT'] = 'http://local'

        try:
            loader = ConfigLoader(config_dir)
            with pytest.raises(ConfigError, match='Configuration validation failed'):
                loader.load(Environment.DEVELOPMENT)
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_production_requires_switches(self, tmp_path) -> None:
        """Test that production requires certain switches enabled."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()

        # Copy schema (go up 5 levels: tests/unit/core/config -> tests/unit/core -> tests/unit -> tests -> project root)
        schema = yaml.safe_load(
            (
                Path(__file__).parent.parent.parent.parent.parent / 'config' / 'schema.yaml'
            ).read_text()
        )
        (config_dir / 'schema.yaml').write_text(yaml.dump(schema))

        # Prod config with reranker disabled
        env_config = {
            'app': {'environment': 'production'},
            'switches': {'reranker_enabled': False},
            'caches': {
                'answer_cache': {
                    'table_name': '${ANSWER_CACHE_TABLE}',
                    'max_entry_size_bytes': 400000,
                },
                'role_cache': {'table_name': '${ROLE_CACHE_TABLE}', 'max_entry_size_bytes': 400000},
            },
        }
        (config_dir / 'prod.yaml').write_text(yaml.dump(env_config))

        # Set required env vars
        os.environ['VECTOR_DB_HOST'] = 'prod-host'
        os.environ['VECTOR_DB_NAME'] = 'prod'
        os.environ['VECTOR_DB_USER'] = 'prod'
        os.environ['VECTOR_DB_PASSWORD'] = 'prod'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'prod-answers'
        os.environ['ROLE_CACHE_TABLE'] = 'prod-roles'
        os.environ['INGESTION_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123/prod-ingestion'
        os.environ['REPROCESSING_QUEUE_URL'] = (
            'https://sqs.us-east-1.amazonaws.com/123/prod-reprocessing'
        )
        os.environ['REPORTS_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123/prod-reports'
        os.environ['DLQ_URL'] = 'https://sqs.us-east-1.amazonaws.com/123/prod-dlq'
        os.environ['DOCUMENTS_BUCKET'] = 'prod-docs'
        os.environ['REPORTS_BUCKET'] = 'prod-reports'
        os.environ['BACKUPS_BUCKET'] = 'prod-backups'
        os.environ['COGNITO_USER_POOL_ID'] = 'prod-pool'
        os.environ['COGNITO_CLIENT_ID'] = 'prod-client'
        os.environ['METERING_TABLE'] = 'prod-metering'
        os.environ['OTLP_ENDPOINT'] = 'https://otel.example.com'

        try:
            loader = ConfigLoader(config_dir)
            with pytest.raises(ConfigError, match='reranker_enabled must be true in production'):
                loader.load(Environment.PRODUCTION)
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_config_singleton(self) -> None:
        """Test that get_config returns singleton after load."""
        os.environ['VECTOR_DB_HOST'] = 'localhost'
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test'
        os.environ['ROLE_CACHE_TABLE'] = 'test'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/q'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/q'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/q'
        os.environ['DLQ_URL'] = 'http://local/q'
        os.environ['DOCUMENTS_BUCKET'] = 'test'
        os.environ['REPORTS_BUCKET'] = 'test'
        os.environ['BACKUPS_BUCKET'] = 'test'
        os.environ['COGNITO_USER_POOL_ID'] = 'test'
        os.environ['COGNITO_CLIENT_ID'] = 'test'
        os.environ['METERING_TABLE'] = 'test'
        os.environ['OTLP_ENDPOINT'] = 'http://local'

        try:
            config1 = load_config(Environment.DEVELOPMENT)
            config2 = get_config()
            assert config1 is config2  # Same object
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_get_config_before_load_raises(self) -> None:
        """Test that get_config before load raises."""
        reset_config()
        with pytest.raises(ConfigError, match='Configuration not loaded'):
            get_config()


class TestConfigValidation:
    """Tests for config validation rules."""

    def setup_method(self) -> None:
        reset_config()

    def teardown_method(self) -> None:
        reset_config()

    def test_pool_size_validation(self, tmp_path) -> None:
        """Test that max_overflow <= pool_size is validated."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()

        # Copy schema (go up 5 levels: tests/unit/core/config -> tests/unit/core -> tests/unit -> tests -> project root)
        schema = yaml.safe_load(
            (
                Path(__file__).parent.parent.parent.parent.parent / 'config' / 'schema.yaml'
            ).read_text()
        )
        (config_dir / 'schema.yaml').write_text(yaml.dump(schema))

        env_config = {
            'app': {'environment': 'development'},
            'vector_store': {'pool_size': 5, 'max_overflow': 10},  # Invalid: overflow > pool
            'caches': {
                'answer_cache': {
                    'table_name': '${ANSWER_CACHE_TABLE}',
                    'max_entry_size_bytes': 400000,
                },
                'role_cache': {'table_name': '${ROLE_CACHE_TABLE}', 'max_entry_size_bytes': 400000},
            },
        }
        (config_dir / 'dev.yaml').write_text(yaml.dump(env_config))

        os.environ['VECTOR_DB_HOST'] = 'localhost'
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test'
        os.environ['ROLE_CACHE_TABLE'] = 'test'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/q'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/q'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/q'
        os.environ['DLQ_URL'] = 'http://local/q'
        os.environ['DOCUMENTS_BUCKET'] = 'test'
        os.environ['REPORTS_BUCKET'] = 'test'
        os.environ['BACKUPS_BUCKET'] = 'test'
        os.environ['COGNITO_USER_POOL_ID'] = 'test'
        os.environ['COGNITO_CLIENT_ID'] = 'test'
        os.environ['METERING_TABLE'] = 'test'
        os.environ['OTLP_ENDPOINT'] = 'http://local'

        try:
            loader = ConfigLoader(config_dir)
            with pytest.raises(ConfigError, match='max_overflow must be <= pool_size'):
                loader.load(Environment.DEVELOPMENT)
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]

    def test_fallback_model_limit(self, tmp_path) -> None:
        """Test that max 3 fallback models enforced."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()

        # Copy schema (go up 5 levels: tests/unit/core/config -> tests/unit/core -> tests/unit -> tests -> project root)
        schema = yaml.safe_load(
            (
                Path(__file__).parent.parent.parent.parent.parent / 'config' / 'schema.yaml'
            ).read_text()
        )
        (config_dir / 'schema.yaml').write_text(yaml.dump(schema))

        # Create 4 fallback models
        fallbacks = []
        for i in range(4):
            fallbacks.append(
                {
                    'provider': 'litellm',
                    'model_id': f'model-{i}',
                    'max_tokens': 4096,
                    'temperature': 0.0,
                    'timeout_seconds': 30,
                    'max_retries': 2,
                    'retry_base_delay_seconds': 1.0,
                }
            )

        env_config = {'app': {'environment': 'development'}, 'llm': {'fallback_models': fallbacks}}
        (config_dir / 'dev.yaml').write_text(yaml.dump(env_config))

        os.environ['VECTOR_DB_HOST'] = 'localhost'
        os.environ['VECTOR_DB_NAME'] = 'test'
        os.environ['VECTOR_DB_USER'] = 'test'
        os.environ['VECTOR_DB_PASSWORD'] = 'test'
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['ANSWER_CACHE_TABLE'] = 'test'
        os.environ['ROLE_CACHE_TABLE'] = 'test'
        os.environ['INGESTION_QUEUE_URL'] = 'http://local/q'
        os.environ['REPROCESSING_QUEUE_URL'] = 'http://local/q'
        os.environ['REPORTS_QUEUE_URL'] = 'http://local/q'
        os.environ['DLQ_URL'] = 'http://local/q'
        os.environ['DOCUMENTS_BUCKET'] = 'test'
        os.environ['REPORTS_BUCKET'] = 'test'
        os.environ['BACKUPS_BUCKET'] = 'test'
        os.environ['COGNITO_USER_POOL_ID'] = 'test'
        os.environ['COGNITO_CLIENT_ID'] = 'test'
        os.environ['METERING_TABLE'] = 'test'
        os.environ['OTLP_ENDPOINT'] = 'http://local'

        try:
            loader = ConfigLoader(config_dir)
            with pytest.raises(ConfigError, match='Maximum 3 fallback models allowed'):
                loader.load(Environment.DEVELOPMENT)
        finally:
            for key in list(os.environ.keys()):
                if key in [
                    'VECTOR_DB_HOST',
                    'VECTOR_DB_NAME',
                    'VECTOR_DB_USER',
                    'VECTOR_DB_PASSWORD',
                    'AWS_REGION',
                    'ANSWER_CACHE_TABLE',
                    'ROLE_CACHE_TABLE',
                    'INGESTION_QUEUE_URL',
                    'REPROCESSING_QUEUE_URL',
                    'REPORTS_QUEUE_URL',
                    'DLQ_URL',
                    'DOCUMENTS_BUCKET',
                    'REPORTS_BUCKET',
                    'BACKUPS_BUCKET',
                    'COGNITO_USER_POOL_ID',
                    'COGNITO_CLIENT_ID',
                    'METERING_TABLE',
                    'OTLP_ENDPOINT',
                ]:
                    del os.environ[key]
