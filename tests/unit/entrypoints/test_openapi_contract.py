"""Contract checks for the published OpenAPI document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finsight.entrypoints.api.app import create_app


def _walk_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref' and isinstance(item, str):
                refs.append(item)
            else:
                refs.extend(_walk_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_walk_refs(item))
    return refs


def test_every_local_openapi_reference_resolves() -> None:
    schema = create_app().openapi()

    unresolved = [
        ref for ref in _walk_refs(schema) if ref.startswith('#/') and _resolve(schema, ref) is None
    ]

    assert unresolved == []


def _resolve(schema: dict[str, Any], ref: str) -> Any:
    current: Any = schema
    for part in ref.removeprefix('#/').split('/'):
        token = part.replace('~1', '/').replace('~0', '~')
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def test_ask_stream_declares_typed_event_schema() -> None:
    schema = create_app().openapi()

    event_schema = schema['components']['schemas']['AskQuestionEvent']
    ask_response = schema['paths']['/ask']['post']['responses']['200']

    assert event_schema['properties']['event']['type'] == 'string'
    assert event_schema['properties']['data']['type'] == 'object'
    assert ask_response['content']['text/event-stream']['schema'] == {
        '$ref': '#/components/schemas/AskQuestionEvent'
    }


def test_committed_contract_can_be_parsed() -> None:
    committed = json.loads(Path('docs/openapi.json').read_text(encoding='utf-8'))
    assert committed['info']['title'] == 'FinSight AI API'
