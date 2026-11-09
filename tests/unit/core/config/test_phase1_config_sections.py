"""Typed Phase 1 config sections."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finsight.core.config import (
    AccessConfig,
    AnswerCheckConfig,
    CacheConfig,
    Config,
    ConsistencyConfig,
    DatabaseConfig,
    EdgeConfig,
    EncryptionConfig,
    LambdaConfig,
    MeteringConfig,
    ModelsConfig,
    ModelsEmbeddingConfig,
    ModelsRerankConfig,
    ProtectionConfig,
    ScaleConfig,
    TrafficConfig,
)


def test_database_defaults() -> None:
    section = DatabaseConfig()
    assert section.engine == 'aurora_postgres'
    assert section.min_capacity_acu == 0.0


def test_traffic_defaults() -> None:
    section = TrafficConfig()
    assert section.lambda_reserved_concurrency == 20


def test_protection_defaults() -> None:
    section = ProtectionConfig()
    assert section.waf_enabled is False


def test_encryption_requires_kms_alias() -> None:
    with pytest.raises(ValidationError):
        EncryptionConfig(key_mode='kms_customer', kms_key_alias='')
    assert EncryptionConfig().key_mode == 'aws_managed'


def test_lambda_defaults() -> None:
    section = LambdaConfig()
    assert section.question_provisioned_concurrency == 0


def test_models_defaults() -> None:
    assert ModelsConfig.model_fields['timeout_seconds'].default == 20
    assert ModelsConfig.model_fields['answer'].is_required() is True
    assert ModelsEmbeddingConfig.model_fields['dimensions'].default == 1024
    assert ModelsRerankConfig.model_fields['timeout_ms'].default == 600


def test_cache_defaults() -> None:
    section = CacheConfig()
    assert section.answer_enabled is True
    assert section.ttl_seconds == 3600


def test_edge_defaults() -> None:
    section = EdgeConfig()
    assert section.http3_enabled is True


def test_scale_defaults() -> None:
    section = ScaleConfig()
    assert section.cells == 1
    assert section.queue_priority == 'quick_first'


def test_answer_check_defaults() -> None:
    section = AnswerCheckConfig()
    assert section.enabled is True
    assert section.retry_max == 1
    assert section.retry_time_limit_seconds == 4


def test_metering_defaults() -> None:
    section = MeteringConfig(table_name='t')
    assert section.shared_cost_split == 'requests_and_runtime'
    assert section.reconcile_tolerance_percent == 10


def test_consistency_defaults() -> None:
    section = ConsistencyConfig()
    assert section.job_max_receive_count == 5


def test_access_defaults() -> None:
    section = AccessConfig()
    assert section.users_per_company_max == 10


def test_unknown_key_rejected() -> None:
    with pytest.raises(ValidationError):
        DatabaseConfig(unknown_field=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        TrafficConfig(foo='bar')  # type: ignore[call-arg]


def test_config_extended_sections_optional() -> None:
    # Minimal config still validates extended sections as None
    # (full config requires other core sections, so check direct optionality)
    assert DatabaseConfig is not None
    assert Config.__fields__['database'].is_required() is False
