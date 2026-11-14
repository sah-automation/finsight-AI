"""Verify the real JSON span log shape matches the §15 metric filter paths (issue #276).

The Observability stack's CloudWatch metric filters target ``$.span.attributes.*``.
The tracing adapter emits a structured JSON log record whose ``span`` extra nests
the alert fields under ``attributes``. These tests lock that contract: if the log
shape or the field names drift, the filters silently stop matching.
"""

from __future__ import annotations

import asyncio
import json
import logging

from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.core.logging import TraceFormatter

ALERT_SPAN_ATTRIBUTES: dict[str, object] = {
    'fallback_3_used': True,
    'reranker_down': True,
    'alert': 'reranker_down',
    'embedding_retries': 3,
    'job_in_retry_list': True,
    'role_cache_stale_seconds': 7200,
}

# The exact JSON paths the five §15 metric filters inspect (see
# infra/cdk/stacks/observability.py).
METRIC_FILTER_PATHS: tuple[str, ...] = (
    '$.span.attributes.fallback_3_used',
    '$.span.attributes.reranker_down',
    '$.span.attributes.embedding_retries',
    '$.span.attributes.job_in_retry_list',
    '$.span.attributes.role_cache_stale_seconds',
)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _emitted_span_record() -> dict[str, object]:
    adapter = TracingAdapter(service_name='finsight-ai', enabled=True)
    logger = logging.getLogger('finsight.adapters.tracing.tracing_adapter')
    handler = _CaptureHandler()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        asyncio.run(
            adapter.start_span('company_123', 'llm_call', attributes=dict(ALERT_SPAN_ATTRIBUTES))
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    formatter = TraceFormatter(
        '%(timestamp)s %(level)s %(logger)s %(message)s',
        rename_fields={'levelname': 'level'},
    )
    span_records = [
        json.loads(formatter.format(record))
        for record in handler.records
        if 'tracing span emitted' in record.getMessage()
    ]
    assert span_records, 'expected a "tracing span emitted" log record'
    return span_records[-1]


def _resolve(record: dict[str, object], path: str) -> object | None:
    node: object = record
    for part in path.removeprefix('$.').split('.'):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def test_span_log_record_nests_alert_fields_under_span_attributes() -> None:
    record = _emitted_span_record()
    attributes = record['span']['attributes']  # type: ignore[index]
    for field, value in ALERT_SPAN_ATTRIBUTES.items():
        assert attributes[field] == value, f'{field} missing from span.attributes'


def test_metric_filter_paths_resolve_against_real_span_record() -> None:
    record = _emitted_span_record()
    for path in METRIC_FILTER_PATHS:
        assert _resolve(record, path) is not None, f'metric filter path {path} does not resolve'
