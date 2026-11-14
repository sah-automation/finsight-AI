"""Synthesis tests for the observability / CloudWatch alert stack (issue #112)."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.observability import (
    ALERT_MAPPINGS,
    ALERT_SIGNALS,
    ObservabilityStack,
)


def _template(env_name: str) -> Template:
    app = cdk.App()
    stack = ObservabilityStack(app, f'FinSight-{env_name}-Observability', env_name=env_name)
    return Template.from_stack(stack)


def test_log_group_is_defined() -> None:
    template = _template('dev')
    groups = template.find_resources('AWS::Logs::LogGroup')
    assert groups


def test_five_metric_filters_exist() -> None:
    template = _template('dev')
    filters = template.find_resources('AWS::Logs::MetricFilter')
    assert len(filters) == 5  # noqa: PLR2004


def test_five_alarms_exist() -> None:
    template = _template('dev')
    alarms = template.find_resources('AWS::CloudWatch::Alarm')
    assert len(alarms) == 5  # noqa: PLR2004


def test_alert_signals_are_declared() -> None:
    assert len(ALERT_SIGNALS) == 5  # noqa: PLR2004
    assert len(ALERT_MAPPINGS) == 5  # noqa: PLR2004


def test_filters_reference_structured_fields() -> None:
    template = _template('dev')
    patterns = [
        resource['Properties'].get('FilterPattern', '')
        for resource in template.find_resources('AWS::Logs::MetricFilter').values()
    ]
    joined = ' '.join(patterns).lower()
    for field in (
        'fallback_3_used',
        'reranker_down',
        'embedding_retries',
        'job_in_retry_list',
        'role_cache_stale_seconds',
    ):
        assert field in joined


def test_thresholds_match_config() -> None:
    template = _template('dev')
    alarms = list(template.find_resources('AWS::CloudWatch::Alarm').values())
    thresholds = {alarm['Properties']['Threshold'] for alarm in alarms}
    assert {1.0, 3.0, 7200.0}.issubset(thresholds)


def test_no_sensitive_request_content_in_filters() -> None:
    template = _template('dev')
    joined = ' '.join(
        resource['Properties'].get('FilterPattern', '')
        for resource in template.find_resources('AWS::Logs::MetricFilter').values()
    ).lower()
    for forbidden in ('question', 'chunk', 'answer', 'signed_url', 'email', 'pii'):
        assert forbidden not in joined


def test_environment_property_from_template() -> None:
    prod = _template('prod')
    alarms = list(prod.find_resources('AWS::CloudWatch::Alarm').values())
    assert all('finsight-prod' in alarm['Properties']['AlarmName'] for alarm in alarms)


# Each signal maps to the span attribute the tracing adapter nests under
# ``span.attributes`` in the JSON log record (issue #276). CloudWatch OTLP
# ingestion emits exactly this shape, so the filters must target these paths.
_SPAN_ATTRIBUTE_PATHS = {
    'fallback_model_3_used': '$.span.attributes.fallback_3_used',
    'reranker_down': '$.span.attributes.reranker_down',
    'embedding_retries_exceeded': '$.span.attributes.embedding_retries',
    'job_in_retry_list': '$.span.attributes.job_in_retry_list',
    'role_cache_stale_seconds': '$.span.attributes.role_cache_stale_seconds',
}


def test_filters_target_real_span_attribute_paths() -> None:
    template = _template('dev')
    patterns = {
        resource['Properties']['MetricTransformations'][0]['MetricName']: resource['Properties'][
            'FilterPattern'
        ]
        for resource in template.find_resources('AWS::Logs::MetricFilter').values()
    }

    for signal, path in _SPAN_ATTRIBUTE_PATHS.items():
        assert signal in patterns, f'missing metric filter for {signal}'
        assert path in patterns[signal], f'{signal} filter does not match {path}'


def test_every_alert_signal_maps_to_a_span_attribute_path() -> None:
    assert set(_SPAN_ATTRIBUTE_PATHS) == set(ALERT_SIGNALS)
