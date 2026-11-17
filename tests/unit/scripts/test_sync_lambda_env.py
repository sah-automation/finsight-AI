"""Tests for the Lambda environment sync script.

After every CDK deploy the API Lambda's environment is reset to the
CDK-owned set. Secret-backed values (the Neon connection string and the
model-gateway master key) never flow through CDK, so ``sync_lambda_env.py``
re-injects them from SSM into the deployed function. These tests pin the
pure seam: URL parsing, env-var construction and merge semantics.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'sync_lambda_env.py'


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location('sync_lambda_env', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sync_lambda_env = _load_script()


class TestLambdaEnvVars:
    """Building the secret-backed environment variables from SSM values."""

    def test_vector_db_vars_derived_from_neon_url(self) -> None:
        """The Neon URL is decomposed into the VECTOR_DB_* config-loader vars."""
        vars_ = sync_lambda_env.vector_db_vars(
            'postgresql://user:p%40ss@ep-xyz.neon.tech:5432/finsight?sslmode=require'  # pragma: allowlist secret
        )

        assert vars_ == {
            'VECTOR_DB_HOST': 'ep-xyz.neon.tech',
            'VECTOR_DB_PORT': '5432',
            'VECTOR_DB_NAME': 'finsight',
            'VECTOR_DB_USER': 'user',
            'VECTOR_DB_PASSWORD': 'p@ss',  # pragma: allowlist secret
        }

    def test_lambda_env_vars_includes_gateway_token(self) -> None:
        """MODEL_GATEWAY_AUTH_TOKEN is sourced from the master-key parameter."""

        def fake_fetch(name: str, region: str) -> str:
            assert region == 'us-east-1'
            if name == '/finsight/prod/neon/database_url':
                return 'postgresql://u:p@host:5432/db'  # pragma: allowlist secret
            if name == '/finsight/prod/model_gateway_master_key':
                return 'master-key-value'  # pragma: allowlist secret
            raise AssertionError(f'unexpected parameter {name}')

        env_vars = sync_lambda_env.lambda_env_vars(fetch=fake_fetch, env='prod', region='us-east-1')

        assert env_vars['MODEL_GATEWAY_AUTH_TOKEN'] == 'master-key-value'
        assert env_vars['VECTOR_DB_HOST'] == 'host'
        # No secrets in keys other than the documented ones.
        assert set(env_vars) == {
            'VECTOR_DB_HOST',
            'VECTOR_DB_PORT',
            'VECTOR_DB_NAME',
            'VECTOR_DB_USER',
            'VECTOR_DB_PASSWORD',
            'MODEL_GATEWAY_AUTH_TOKEN',
        }

    def test_missing_master_key_param_fails_loudly(self) -> None:
        """A missing parameter must abort the sync, never deploy a half env."""

        def fake_fetch(name: str, region: str) -> str:
            raise KeyError(name)

        with pytest.raises(KeyError):
            sync_lambda_env.lambda_env_vars(fetch=fake_fetch, env='prod', region='us-east-1')

    def test_placeholder_master_key_fails_loudly(self) -> None:
        """The CDK scaffold value must never reach the deployed function.

        CDK creates the master-key parameter with a placeholder for fresh
        environments; the real key is set in SSM as a one-time rotation.
        Syncing the placeholder would make every gateway call fail with
        401 while looking "configured".
        """

        def fake_fetch(name: str, region: str) -> str:
            if name.endswith('neon/database_url'):
                return 'postgresql://u:p@host:5432/db'  # pragma: allowlist secret
            return 'PLACEHOLDER_REPLACE_AT_DEPLOY'

        with pytest.raises(RuntimeError, match='model_gateway_master_key'):
            sync_lambda_env.lambda_env_vars(fetch=fake_fetch, env='prod', region='us-east-1')


class TestMergeEnv:
    """Merging secret vars into the deployed function's environment."""

    def test_merge_preserves_existing_cdk_vars(self) -> None:
        """CDK-managed vars must survive; sync vars win on conflict."""
        existing = {
            'ENVIRONMENT': 'production',
            'DOCUMENTS_BUCKET': 'finsight-prod-documents',
            'VECTOR_DB_HOST': 'stale-value',
        }
        synced = {'VECTOR_DB_HOST': 'ep-xyz.neon.tech', 'MODEL_GATEWAY_AUTH_TOKEN': 'k'}

        merged = sync_lambda_env.merge_lambda_env(existing, synced)

        assert merged['ENVIRONMENT'] == 'production'
        assert merged['DOCUMENTS_BUCKET'] == 'finsight-prod-documents'
        assert merged['VECTOR_DB_HOST'] == 'ep-xyz.neon.tech'
        assert merged['MODEL_GATEWAY_AUTH_TOKEN'] == 'k'
        assert len(merged) == 4

    def test_merge_does_not_mutate_inputs(self) -> None:
        existing = {'ENVIRONMENT': 'production'}
        merged = sync_lambda_env.merge_lambda_env(existing, {'VECTOR_DB_HOST': 'h'})

        assert existing == {'ENVIRONMENT': 'production'}
        assert 'VECTOR_DB_HOST' in merged

    def test_default_function_name_matches_compute_stack(self) -> None:
        """The target function name mirrors the CDK compute stack naming."""
        assert sync_lambda_env.default_function_name('prod') == 'finsight-prod-api'
