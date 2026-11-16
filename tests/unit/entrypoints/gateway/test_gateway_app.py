"""Tests for the model-gateway FastAPI bridge (issue #330).

The bridge is the remote implementation of the LLM/embedding surface: it
receives litellm-shaped JSON bodies, calls the gateway adapter (which in turn
calls litellm in-process), and answers with litellm-shaped JSON — chat
completions streamed as NDJSON lines, embeddings buffered. Every test
monkeypatches the adapter; no network.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

import finsight.adapters.gateway as gateway_adapter_module
from finsight.entrypoints.gateway import app as gateway_app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture()
def client() -> TestClient:
    return TestClient(gateway_app.app)


@pytest.fixture()
def no_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway_app, 'runtime_settings', dict)
    # Clear the SSM cache on the adapter module
    monkeypatch.setattr(gateway_adapter_module, '_MASTER_KEY_CACHE', None)


@pytest.fixture()
def with_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway_app, 'runtime_settings', lambda: {'master_key': 'secret-key'})
    # Set the SSM cache on the adapter module
    monkeypatch.setattr(gateway_adapter_module, '_MASTER_KEY_CACHE', 'secret-key')


@pytest.fixture(autouse=True)
def _reset_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the lazy adapter factory between tests."""
    monkeypatch.setattr(gateway_app, '_adapter_factory', None)
    monkeypatch.setattr(gateway_adapter_module, '_MASTER_KEY_CACHE', None)


CHAT_CHUNKS: list[dict[str, Any]] = [
    {'choices': [{'delta': {'content': 'Hel'}}], 'model': 'groq/openai/gpt-oss-120b'},
    {'choices': [{'delta': {'content': 'lo'}}], 'model': 'groq/openai/gpt-oss-120b'},
]

CHAT_BODY: dict[str, Any] = {
    'model': 'groq/openai/gpt-oss-120b',
    'messages': [{'role': 'user', 'content': 'hello'}],
    'stream': True,
}

EMBEDDING_RESPONSE: dict[str, Any] = {
    'data': [{'embedding': [0.1, 0.2], 'index': 0}],
    'model': 'gemini/gemini-embedding-001',
    'usage': {'prompt_tokens': 1, 'total_tokens': 1},
}


@pytest.mark.unit
class TestGatewayHealth:
    """The readiness endpoint the Web Adapter polls."""

    def test_healthz_is_ok(self, client: TestClient, no_master_key: None) -> None:
        response = client.get('/healthz')

        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}


@pytest.mark.unit
class TestChatCompletionsBridge:
    """POST /v1/chat/completions streams litellm chunks as NDJSON."""

    def test_streams_litellm_shaped_ndjson(
        self, client: TestClient, no_master_key: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_chat(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
            assert kwargs['model'] == CHAT_BODY['model']
            assert kwargs['stream'] is True
            for chunk in CHAT_CHUNKS:
                yield chunk

        mock_adapter = type('MockAdapter', (), {'chat_completions': fake_chat})()
        monkeypatch.setattr(gateway_app, '_adapter_factory', lambda: mock_adapter)

        with client.stream('POST', '/v1/chat/completions', json=CHAT_BODY) as response:
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('application/x-ndjson')
            lines = [line for line in response.iter_lines() if line.strip()]

        assert [json.loads(line) for line in lines] == CHAT_CHUNKS

    def test_provider_failure_is_loud(
        self, client: TestClient, no_master_key: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def failing_chat(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError('provider unavailable')
            yield {}  # pragma: no cover

        mock_adapter = type('MockAdapter', (), {'chat_completions': failing_chat})()
        monkeypatch.setattr(gateway_app, '_adapter_factory', lambda: mock_adapter)

        response = client.post('/v1/chat/completions', json=CHAT_BODY)

        assert response.status_code == 502


@pytest.mark.unit
class TestEmbeddingsBridge:
    """POST /v1/embeddings returns the litellm-shaped response dict."""

    def test_returns_litellm_shaped_response(
        self, client: TestClient, no_master_key: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        async def fake_embeddings(self: Any, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return EMBEDDING_RESPONSE

        mock_adapter = type('MockAdapter', (), {'embeddings': fake_embeddings})()
        monkeypatch.setattr(gateway_app, '_adapter_factory', lambda: mock_adapter)

        response = client.post(
            '/v1/embeddings',
            json={'model': 'gemini/gemini-embedding-001', 'input': ['a'], 'dimensions': 1024},
        )

        assert response.status_code == 200
        assert response.json() == EMBEDDING_RESPONSE
        assert captured['model'] == 'gemini/gemini-embedding-001'
        assert captured['dimensions'] == 1024


@pytest.mark.unit
class TestMasterKeyCheck:
    """When a master key is configured, requests must present it."""

    def test_rejects_missing_key(self, client: TestClient, with_master_key: None) -> None:
        response = client.get('/healthz')

        assert response.status_code == 401

    def test_rejects_wrong_key(self, client: TestClient, with_master_key: None) -> None:
        response = client.get('/healthz', headers={'X-Gateway-Master-Key': 'nope'})

        assert response.status_code == 401

    def test_accepts_correct_key(self, client: TestClient, with_master_key: None) -> None:
        response = client.get('/healthz', headers={'X-Gateway-Master-Key': 'secret-key'})

        assert response.status_code == 200
