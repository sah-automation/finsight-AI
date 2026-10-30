"""CDK stack: observability, structured CloudWatch log group, and alert mappings.

Exposes one log group for the application runtime and a CloudWatch alarm per
degradation signal. Alarms are driven by metric filters over the structured
JSON fields emitted by tracing and metering; they never inspect free-form
request text, answers, PII, or signed URLs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_logs as logs
from constructs import Construct

__all__ = [
    'ALERT_MAPPINGS',
    'ALERT_NAMES',
    'ALERT_SIGNALS',
    'CLOUDWATCH_ALERTS',
    'REQUIRED_ALERT_SIGNALS',
    'ObservabilityStack',
]

# The five degradation signals requiring operator visibility. Names match the
# structured fields already emitted by tracing/metering and the alert switches
# in ``config/*.yaml``.
ALERT_SIGNALS: tuple[str, ...] = (
    'fallback_model_3_used',
    'reranker_down',
    'embedding_retries_exceeded',
    'job_in_retry_list',
    'role_cache_stale_seconds',
)
REQUIRED_ALERT_SIGNALS = ALERT_SIGNALS
ALERT_NAMES = ALERT_SIGNALS
CLOUDWATCH_ALERTS = ALERT_SIGNALS

# Mapping of alert signal -> (structured log field, threshold key, default).
_ALERT_DEFAULTS: dict[str, dict[str, Any]] = {
    'fallback_model_3_used': {
        'log_field': 'fallback_3_used',
        'threshold': 1,
        'comparison': 'boolean',
        'metric_value': '1',
    },
    'reranker_down': {
        'log_field': 'alert',
        'threshold': 1,
        'comparison': 'string',
        'metric_value': '1',
        'match_value': 'reranker_down',
    },
    'embedding_retries_exceeded': {
        'log_field': 'embedding_retries',
        'threshold': 3,
        'comparison': 'number',
        'metric_value': '$.embedding_retries',
    },
    'job_in_retry_list': {
        'log_field': 'job_in_retry_list',
        'threshold': 1,
        'comparison': 'boolean',
        'metric_value': '1',
    },
    'role_cache_stale_seconds': {
        'log_field': 'role_cache_stale_seconds',
        'threshold': 7200,
        'comparison': 'number',
        'metric_value': '$.role_cache_stale_seconds',
    },
}

ALERT_MAPPINGS: dict[str, dict[str, Any]] = _ALERT_DEFAULTS


def _load_alert_thresholds(env_name: str) -> dict[str, Any]:
    """Load alert thresholds from application config when available."""

    thresholds = {
        'fallback_model_3_used': 1,
        'reranker_down': 1,
        'embedding_retries_exceeded': 3,
        'job_in_retry_list': 1,
        'role_cache_stale_seconds': 7200,
    }

    # Application config is optional for synthesis; fall back to the defaults
    # above when it cannot be located or parsed.
    candidates = [
        Path(__file__).resolve().parents[3] / 'config' / f'{env_name}.yaml',
        Path.cwd().parents[1] / 'config' / f'{env_name}.yaml',
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        data = yaml.safe_load(candidate.read_text(encoding='utf-8')) or {}
        alerts = (data.get('observability') or {}).get('alerts') if isinstance(data, dict) else None
        if not isinstance(alerts, dict):
            continue
        if isinstance(alerts.get('fallback_model_3_used'), bool):
            thresholds['fallback_model_3_used'] = 1 if alerts['fallback_model_3_used'] else 0
        if isinstance(alerts.get('reranker_down'), bool):
            thresholds['reranker_down'] = 1 if alerts['reranker_down'] else 0
        if isinstance(alerts.get('embedding_retries_exceeded'), int):
            thresholds['embedding_retries_exceeded'] = alerts['embedding_retries_exceeded']
        if isinstance(alerts.get('job_in_retry_list'), bool):
            thresholds['job_in_retry_list'] = 1 if alerts['job_in_retry_list'] else 0
        if isinstance(alerts.get('role_cache_stale_seconds'), int):
            thresholds['role_cache_stale_seconds'] = alerts['role_cache_stale_seconds']
    return thresholds


class ObservabilityStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, env_name: str, **kwargs: object
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        retention = RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY

        self.log_group = logs.LogGroup(
            self,
            f'AppLogGroup{env_name}',
            log_group_name=f'/aws/lambda/finsight-{env_name}',
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=retention,
        )

        thresholds = _load_alert_thresholds(env_name)
        namespace = f'FinSight/{env_name}'
        period = Duration.minutes(5)

        self.metric_filters: dict[str, logs.MetricFilter] = {}
        self.alarms: dict[str, cloudwatch.Alarm] = {}

        # 1. Fallback model 3 was used.
        self.metric_filters['fallback_model_3_used'] = logs.MetricFilter(
            self,
            'FallbackModel3UsedMetricFilter',
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(
                '{ ($.fallback_3_used = true) || ($.span.attributes.fallback_3_used = true) }'
            ),
            metric_name='fallback_model_3_used',
            metric_namespace=namespace,
            metric_value='1',
        )
        self.alarms['fallback_model_3_used'] = cloudwatch.Alarm(
            self,
            'FallbackModel3UsedAlarm',
            alarm_name=f'finsight-{env_name}-fallback-model-3-used',
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name='fallback_model_3_used',
                statistic='Sum',
                period=period,
            ),
            threshold=float(thresholds['fallback_model_3_used']),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # 2. Reranker fell back to search order (reranker down).
        self.metric_filters['reranker_down'] = logs.MetricFilter(
            self,
            'RerankerDownMetricFilter',
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(
                '{ ($.reranker_down = true) || ($.alert = "reranker_down") || ($.span.attributes.reranker_down = true) || ($.span.attributes.alert = "reranker_down") }'  # noqa: E501
            ),
            metric_name='reranker_down',
            metric_namespace=namespace,
            metric_value='1',
        )
        self.alarms['reranker_down'] = cloudwatch.Alarm(
            self,
            'RerankerDownAlarm',
            alarm_name=f'finsight-{env_name}-reranker-down',
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name='reranker_down',
                statistic='Sum',
                period=period,
            ),
            threshold=float(thresholds['reranker_down']),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # 3. Embedding retries exceeded the configured bound.
        self.metric_filters['embedding_retries_exceeded'] = logs.MetricFilter(
            self,
            'EmbeddingRetriesExceededMetricFilter',
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(
                '{ ($.embedding_retries >= 1) || ($.span.attributes.embedding_retries >= 1) }'
            ),
            metric_name='embedding_retries_exceeded',
            metric_namespace=namespace,
            metric_value='$.embedding_retries',
        )
        self.alarms['embedding_retries_exceeded'] = cloudwatch.Alarm(
            self,
            'EmbeddingRetriesExceededAlarm',
            alarm_name=f'finsight-{env_name}-embedding-retries-exceeded',
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name='embedding_retries_exceeded',
                statistic='Sum',
                period=period,
            ),
            threshold=float(thresholds['embedding_retries_exceeded']),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # 4. A job landed in the retry list.
        self.metric_filters['job_in_retry_list'] = logs.MetricFilter(
            self,
            'JobInRetryListMetricFilter',
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(
                '{ ($.job_in_retry_list = true) || ($.span.attributes.job_in_retry_list = true) }'
            ),
            metric_name='job_in_retry_list',
            metric_namespace=namespace,
            metric_value='1',
        )
        self.alarms['job_in_retry_list'] = cloudwatch.Alarm(
            self,
            'JobInRetryListAlarm',
            alarm_name=f'finsight-{env_name}-job-in-retry-list',
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name='job_in_retry_list',
                statistic='Sum',
                period=period,
            ),
            threshold=float(thresholds['job_in_retry_list']),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # 5. Role cache entries are stale.
        self.metric_filters['role_cache_stale_seconds'] = logs.MetricFilter(
            self,
            'RoleCacheStaleMetricFilter',
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(
                '{ ($.role_cache_stale_seconds >= 1) || ($.span.attributes.role_cache_stale_seconds >= 1) }'  # noqa: E501
            ),
            metric_name='role_cache_stale_seconds',
            metric_namespace=namespace,
            metric_value='$.role_cache_stale_seconds',
        )
        self.alarms['role_cache_stale_seconds'] = cloudwatch.Alarm(
            self,
            'RoleCacheStaleAlarm',
            alarm_name=f'finsight-{env_name}-role-cache-stale',
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name='role_cache_stale_seconds',
                statistic='Maximum',
                period=period,
            ),
            threshold=float(thresholds['role_cache_stale_seconds']),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
