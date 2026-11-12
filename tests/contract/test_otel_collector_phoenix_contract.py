"""Contract tests: local Phoenix export path with a redacting collector (#280).

The local development stack exports spans through the OTel collector to Arize
Phoenix. This contract pins the three artifacts of that path:

- ``infra/otel/collector.yaml`` runs an ``attributes/redact`` processor that
  mirrors the application's sensitive-field redaction blocklist before spans
  are exported, and exports traces to the Phoenix service.
- ``docker-compose.test.yml`` runs Phoenix in SQLite mode next to the
  collector, and the collector only starts after Phoenix is healthy.
- ``config/dev.yaml`` sends development traces to the collector's OTLP HTTP
  receiver (the redacting gateway in front of Phoenix), not around it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from finsight.adapters.tracing import STANDARD_SPAN_ATTRIBUTES
from finsight.adapters.tracing._tracing_redaction import REDACTED_SPAN_FIELDS
from finsight.core.logging.redaction import SENSITIVE_FIELD_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ config loading


def _collector_config() -> dict[str, Any]:
    path = REPO_ROOT / 'infra' / 'otel' / 'collector.yaml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def _compose() -> dict[str, Any]:
    path = REPO_ROOT / 'docker-compose.test.yml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def _dev_config() -> dict[str, Any]:
    path = REPO_ROOT / 'config' / 'dev.yaml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))


# ------------------------------------------------------------------ helpers

# Attribute names emitted by the traced decorators when the
# llm_content_capture_enabled switch is on (see traced_llm.py,
# traced_embedding.py and traced_reranker.py). They carry full LLM content on
# purpose (opt-in capture, ADR 0005) and must survive collector redaction.
GENAI_CONTENT_ATTRIBUTES = (
    'genai.request.messages',
    'genai.response.messages',
    'genai.embedding.texts',
    'genai.rerank.query',
    'genai.rerank.candidates',
)

# Aggregate LLM metric names that legitimately contain the 'token'/'prompt'
# substrings and must survive redaction (mirrors the metric allow-list in
# src/finsight/adapters/tracing/_tracing_redaction.py).
TOKEN_METRIC_ATTRIBUTES = (
    'first_token_latency_ms',
    'tokens_prompt',
    'tokens_completion',
    'tokens_total',
    'prompt_tokens',
    'completion_tokens',
    'total_tokens',
    'input_tokens',
    'output_tokens',
    'token_count',
)


def _redaction_actions() -> list[dict[str, Any]]:
    processors = _collector_config()['processors']
    assert 'attributes/redact' in processors, 'collector config has no attributes/redact processor'
    actions = processors['attributes/redact'].get('actions')
    assert isinstance(actions, list) and actions, 'attributes/redact has no actions'
    return actions


def _apply_redaction_actions(
    attributes: dict[str, Any], actions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply the collector's delete actions to a span attribute map.

    Mirrors opentelemetry-collector-contrib attributesprocessor delete
    semantics for the actions used here: exact key deletion, and unanchored
    regex search against the attribute key for pattern deletion.
    """
    remaining = dict(attributes)
    for action in actions:
        if action.get('action') != 'delete':
            continue
        pattern = action.get('pattern')
        if pattern is not None:
            regex = re.compile(pattern)
            remaining = {key: value for key, value in remaining.items() if not regex.search(key)}
        elif 'key' in action:
            remaining.pop(str(action['key']), None)
    return remaining


# ------------------------------------------------------------------ collector redaction


def test_traces_pipeline_redacts_before_exporting_to_phoenix() -> None:
    traces = _collector_config()['service']['pipelines']['traces']
    assert 'otlp' in traces['receivers']
    assert 'attributes/redact' in traces['processors'], (
        'traces pipeline must redact attributes before export'
    )
    assert 'otlphttp/phoenix' in traces['exporters'], (
        'traces pipeline must export to the local Phoenix service'
    )


def test_phoenix_exporter_targets_phoenix_http_otlp() -> None:
    exporter = _collector_config()['exporters']['otlphttp/phoenix']
    endpoint = str(exporter['endpoint'])
    assert endpoint.startswith('http://phoenix:'), (
        f'phoenix exporter must target the compose phoenix service, got {endpoint!r}'
    )
    assert endpoint.endswith(':6006'), (
        f'phoenix exporter must target the Phoenix OTLP HTTP port, got {endpoint!r}'
    )


def test_collector_otlp_receiver_listens_on_4318() -> None:
    http = _collector_config()['receivers']['otlp']['protocols']['http']
    assert str(http['endpoint']).endswith(':4318')


def test_redaction_covers_every_blocklist_name() -> None:
    """Every blocklisted span field must be deleted before export."""
    sample: dict[str, Any] = dict.fromkeys(SENSITIVE_FIELD_NAMES, 'leaky-value')
    remaining = _apply_redaction_actions(sample, _redaction_actions())
    assert not remaining, f'blocklisted fields leaked through the collector: {sorted(remaining)}'


def test_redaction_covers_every_blocklist_token() -> None:
    """Every blocklist token must delete matching composite keys.

    The 'token' and 'prompt' tokens are the exception: they are deleted as
    exact attribute names only, because aggregate LLM metric names such as
    'tokens_prompt' legitimately contain those substrings (the application's
    span sanitizer strips composite prompt/token keys before export).
    """
    exact_only = {'token', 'prompt'}
    actions = _redaction_actions()
    for token in REDACTED_SPAN_FIELDS:
        composite_key = f'attr_{token}'
        remaining = _apply_redaction_actions({composite_key: 'leaky-value'}, actions)
        if token in exact_only:
            assert composite_key in remaining, (
                f'exact-name redaction is not supposed to cover {token!r} composites'
            )
        else:
            assert composite_key not in remaining, (
                f'blocklist token {token!r} does not delete matching attribute keys'
            )
    for name in exact_only:
        remaining = _apply_redaction_actions({name: 'leaky-value'}, actions)
        assert name not in remaining, f'blocklisted attribute {name!r} leaked through'


def test_redaction_is_case_insensitive() -> None:
    sample = {'QUESTION': 'leaky', 'Answer_Text': 'leaky', 'Chunk_Text': 'leaky'}
    remaining = _apply_redaction_actions(sample, _redaction_actions())
    assert not remaining, f'uppercase blocklisted fields leaked: {sorted(remaining)}'


def test_redaction_deletes_genai_convention_content_keys() -> None:
    """OTel GenAI semantic-convention content keys must never reach Phoenix.

    gen_ai.prompt.* / gen_ai.completion.* carry full prompt and response
    content but contain no blocklist token, so the collector deletes them by
    prefix. The application's own capture keys use the 'genai.' spelling.
    """
    sample = {
        'gen_ai.prompt.0.content': 'leaky prompt',
        'gen_ai.completion.0.content': 'leaky completion',
        'GEN_AI.PROMPT.1.content': 'leaky uppercase',
    }
    remaining = _apply_redaction_actions(sample, _redaction_actions())
    assert not remaining, f'GenAI convention content keys leaked: {sorted(remaining)}'


def test_redaction_preserves_aggregate_and_content_capture_attributes() -> None:
    survivors = (
        *TOKEN_METRIC_ATTRIBUTES,
        *STANDARD_SPAN_ATTRIBUTES,
        *GENAI_CONTENT_ATTRIBUTES,
    )
    sample: dict[str, Any] = dict.fromkeys(survivors, 'value')
    remaining = _apply_redaction_actions(sample, _redaction_actions())
    assert set(remaining) == set(survivors), (
        f'collector dropped attributes the application keeps: {sorted(set(survivors) - set(remaining))}'
    )


# ------------------------------------------------------------------ compose stack


def test_phoenix_service_runs_sqlite_mode_in_local_stack() -> None:
    services = _compose()['services']
    assert 'phoenix' in services, 'local stack has no phoenix service'
    phoenix = services['phoenix']
    assert phoenix['image'].startswith('arizephoenix/phoenix:version-'), (
        'phoenix image must be pinned to a version tag'
    )
    environment = phoenix.get('environment') or []
    assert 'PHOENIX_WORKING_DIR=/mnt/data' in environment, (
        'phoenix must persist to the SQLite working dir'
    )
    assert not any(str(item).startswith('PHOENIX_SQL_DATABASE_URL=') for item in environment), (
        'phoenix must run in SQLite mode (no external database URL)'
    )
    assert '6006:6006' in (phoenix.get('ports') or []), 'phoenix UI/OTLP HTTP must be published'
    volumes = phoenix.get('volumes') or []
    assert any(str(volume).endswith(':/mnt/data') for volume in volumes), (
        'phoenix SQLite data directory must be a mounted volume'
    )


def test_phoenix_sqlite_volume_is_declared() -> None:
    compose = _compose()
    phoenix = compose['services']['phoenix']
    for volume in phoenix.get('volumes') or []:
        name = str(volume).split(':', 1)[0]
        if name in compose.get('volumes', {}):
            return
    pytest.fail('phoenix data volume is not declared in top-level volumes')


def test_phoenix_has_a_healthcheck() -> None:
    phoenix = _compose()['services']['phoenix']
    healthcheck = phoenix.get('healthcheck')
    assert healthcheck, 'phoenix needs a healthcheck so --wait gates the stack on it'
    assert healthcheck.get('test'), 'phoenix healthcheck has no test command'


def test_collector_mounts_config_and_waits_for_phoenix() -> None:
    collector = _compose()['services']['otel-collector']
    mounts = [str(volume) for volume in collector.get('volumes') or []]
    assert any('infra/otel/collector.yaml' in mount for mount in mounts), (
        'collector must mount infra/otel/collector.yaml'
    )
    depends_on = collector.get('depends_on') or {}
    assert 'phoenix' in depends_on, 'collector must start after phoenix is healthy'


# ------------------------------------------------------------------ dev config


def test_dev_otlp_endpoint_routes_through_redacting_collector() -> None:
    endpoint = _dev_config()['observability']['otlp_endpoint']
    assert endpoint == 'http://localhost:4318/v1/traces', (
        'dev traces must go through the collector OTLP HTTP receiver, which '
        'redacts and exports to Phoenix'
    )
