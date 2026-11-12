"""Validation behavior tests for the Config model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finsight.core.config import Environment, load_config, reset_config
from finsight.core.config.models.config import Config


def _base_config() -> dict:
    reset_config()
    cfg = load_config('test')
    data = cfg.model_dump(mode='python', by_alias=True)
    data['app']['environment'] = cfg.app.environment
    data['traffic'] = {
        'lambda_reserved_concurrency': 20,
        'ingestion_max_concurrency': 4,
        'db_connections_per_request': 3,
        'db_pool_size_per_function': 3,
        'db_pool_timeout_seconds': 10,
        'aurora_max_capacity_acu': 4,
    }
    if data.get('lambda_') is None:
        data['lambda_'] = {}
    if data.get('database') is None:
        data['database'] = {'rds_proxy_enabled': True, 'min_capacity_acu': 1}
    if not data.get('access'):
        # keep existing possibly None; validators skip
        pass
    return data


def _make(data: dict) -> Config:
    return Config.model_validate(data)


class TestProductionRules:
    def test_production_requires_trace_sample_rate(self) -> None:
        data = _base_config()
        data['app']['environment'] = Environment.PRODUCTION
        data['observability']['trace_sample_rate'] = 0.0
        with pytest.raises(ValidationError):
            _make(data)

    def test_production_allows_high_trace_rate(self) -> None:
        data = _base_config()
        data['app']['environment'] = Environment.PRODUCTION
        data['observability']['trace_sample_rate'] = 1.0
        cfg = _make(data)
        assert cfg.app.environment == Environment.PRODUCTION

    def test_production_reranker_disabled_rejected(self) -> None:
        data = _base_config()
        data['app']['environment'] = Environment.PRODUCTION
        data['switches']['reranker_enabled'] = False
        with pytest.raises(ValidationError):
            _make(data)


class TestTrafficRules:
    def test_lambda_concurrency_positive(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config in test environment')
        data['traffic']['lambda_reserved_concurrency'] = 0
        with pytest.raises(ValidationError):
            _make(data)

    def test_db_pool_size_min(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['traffic']['db_pool_size_per_function'] = 0
        with pytest.raises(ValidationError):
            _make(data)

    def test_db_connections_per_request_min(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['traffic']['db_connections_per_request'] = 0
        with pytest.raises(ValidationError):
            _make(data)

    def test_ingestion_max_concurrency_min(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['traffic']['ingestion_max_concurrency'] = 0
        with pytest.raises(ValidationError):
            _make(data)

    def test_ingestion_below_reserved(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['traffic']['lambda_reserved_concurrency'] = 2
        data['traffic']['ingestion_max_concurrency'] = 5
        with pytest.raises(ValidationError):
            _make(data)

    def test_db_pool_at_least_connections_when_parallel(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['switches']['parallel_steps'] = True
        data['traffic']['db_pool_size_per_function'] = 1
        data['traffic']['db_connections_per_request'] = 3
        with pytest.raises(ValidationError):
            _make(data)

    def test_aurora_capacity_min(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        data['traffic']['aurora_max_capacity_acu'] = 0
        with pytest.raises(ValidationError):
            _make(data)

    def test_aurora_capacity_vs_min_acu(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        if data.get('database') is None:
            data['database'] = {}
        data['database']['min_capacity_acu'] = 5
        data['traffic']['aurora_max_capacity_acu'] = 3
        with pytest.raises(ValidationError):
            _make(data)

    def test_conn_limit_requires_proxy_or_headroom(self) -> None:
        # rds_proxy_enabled False with huge needed under limit error
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        if data.get('database') is None:
            data['database'] = {}
        data['database']['rds_proxy_enabled'] = False
        data['traffic']['lambda_reserved_concurrency'] = 100
        data['traffic']['db_pool_size_per_function'] = 10
        data['traffic']['aurora_max_capacity_acu'] = 1
        with pytest.raises(ValidationError):
            _make(data)

    def test_conn_limit_with_proxy_ok(self) -> None:
        data = _base_config()
        if data.get('traffic') is None:
            pytest.skip('no traffic config')
        if data.get('database') is None:
            data['database'] = {}
        data['database']['rds_proxy_enabled'] = True
        cfg = _make(data)
        assert cfg.database.rds_proxy_enabled is True


class TestLambdaRules:
    def test_question_provisioned_le_reserved(self) -> None:
        data = _base_config()
        if data.get('traffic') is None or data.get('lambda_') is None:
            pytest.skip('no traffic/lambda config')
        data['lambda_']['question_provisioned_concurrency'] = (
            data['traffic']['lambda_reserved_concurrency'] + 10
        )
        with pytest.raises(ValidationError):
            _make(data)


class TestModelRules:
    def test_backup_requires_fallbacks(self) -> None:
        data = _base_config()
        if data.get('models') is None:
            pytest.skip('no models config')
        data['models']['backup_request_enabled'] = True
        # clear fallbacks if present
        if data['models'].get('answer'):
            data['models']['answer']['primary_fallbacks'] = []
        with pytest.raises(ValidationError):
            _make(data)


class TestDocumentAndIngestionRules:
    def test_delta_tracking_requires_structure_recursive(self) -> None:
        data = _base_config()
        if not data.get('documents') or not data.get('ingestion'):
            pytest.skip('missing documents/ingestion')
        data['documents']['delta_tracking'] = True
        data['ingestion']['chunk_strategy'] = 'naive'
        with pytest.raises(ValidationError):
            _make(data)

    def test_llm_context_categories_must_be_valid(self) -> None:
        data = _base_config()
        if not data.get('documents') or not data.get('ingestion'):
            pytest.skip('missing')
        data['ingestion']['llm_context_categories'] = ['not-a-category']
        with pytest.raises(ValidationError):
            _make(data)

    def test_categories_must_match_permissions(self) -> None:
        data = _base_config()
        if not data.get('documents') or not data.get('permissions'):
            pytest.skip('missing permissions')
        data['documents']['categories'] = ['x']
        # permissions categories differ
        with pytest.raises(ValidationError):
            _make(data)

    def test_documents_categories_non_empty(self) -> None:
        data = _base_config()
        if not data.get('documents'):
            pytest.skip('missing')
        data['documents']['categories'] = []
        with pytest.raises(ValidationError):
            _make(data)


class TestAccessAndPermissionRules:
    def test_access_roles_must_match_permissions(self) -> None:
        data = _base_config()
        if not data.get('access') or not data.get('permissions'):
            pytest.skip('missing')
        data['access']['roles'] = ['nope']
        with pytest.raises(ValidationError):
            _make(data)

    def test_role_cache_seconds_le_ttl(self) -> None:
        data = _base_config()
        if not data.get('access') or not data.get('caches'):
            pytest.skip('missing')
        if data['caches'].get('role_cache') is None:
            data['caches']['role_cache'] = {}
        data['caches']['role_cache']['ttl_seconds'] = 10
        data['access']['role_cache_seconds_privileged'] = 100
        with pytest.raises(ValidationError):
            _make(data)


class TestSwitchFailLoudRules:
    def test_missing_required_switch_rejected(self) -> None:
        data = _base_config()
        data['switches'].pop('llm_content_capture_enabled')
        with pytest.raises(ValidationError, match='missing required switch'):
            _make(data)

    def test_misspelled_switch_rejected(self) -> None:
        data = _base_config()
        data['switches']['llm_content_capture_enable'] = True
        with pytest.raises(ValidationError):
            _make(data)


class TestSourceViewerSigningKey:
    def test_raises_when_missing(self) -> None:
        data = _base_config()
        data['documents'] = None
        cfg = _make(data)
        with pytest.raises(ValueError):
            _ = cfg.source_viewer_signing_key
