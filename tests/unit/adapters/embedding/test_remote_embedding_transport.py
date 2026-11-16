"""Tests for the remote model-gateway embedding transport (issue #330).

The remote transport plugs into the existing ``embedding_func`` seam of
``LiteLLMEmbedding``: it receives litellm-shaped kwargs (``model``, ``input``,
``timeout``, optional ``dimensions``) and must return a litellm-shaped dict
response with ``data[i].embedding`` vectors. The HTTP layer is injectable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from finsight.adapters.embedding.remote_gateway import (
    RemoteGatewayError,
    build_remote_embedding_func,
)

BASE_SETTINGS = {'base_url': 'https://gw.lambda-url.us-east-1.on.aws', 'region': 'us-east-1'}

EMBEDDING_RESPONSE: dict[str, Any] = {
    'data': [{'embedding': [0.1, 0.2, 0.3], 'index': 0}],
    'model': 'gemini/gemini-embedding-001',
    'usage': {'prompt_tokens': 4, 'total_tokens': 4},
}


def _fake_signer(method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
    """Fake signer for tests: returns headers unchanged (no actual signing)."""
    return dict(headers)


class _FakePostJson:
    """Post-json double: records the request, returns a canned JSON body."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    async def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
    ) -> dict[str, Any]:
        self.requests.append(
            {
                'url': url,
                'headers': dict(headers),
                'body': json.loads(body),
                'timeout': timeout_seconds,
            }
        )
        return self.response


class _ExplodingPostJson:
    """Post-json double that mimics a gateway failure."""

    async def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
    ) -> dict[str, Any]:
        raise RemoteGatewayError(f'gateway POST {url} failed: HTTP 500')


@pytest.mark.unit
class TestRemoteEmbeddingTransport:
    """The embedding transport adapts the gateway HTTP API to litellm shape."""

    async def test_returns_litellm_shaped_response(self) -> None:
        fake = _FakePostJson(EMBEDDING_RESPONSE)
        func = build_remote_embedding_func(BASE_SETTINGS, post_json=fake, signer=_fake_signer)

        result = await func(model='gemini/gemini-embedding-001', input=['a', 'b'], timeout=30)

        assert result == EMBEDDING_RESPONSE
        request = fake.requests[0]
        assert request['url'] == 'https://gw.lambda-url.us-east-1.on.aws/v1/embeddings'
        assert request['body']['model'] == 'gemini/gemini-embedding-001'
        assert request['body']['input'] == ['a', 'b']
        assert request['timeout'] == 30

    async def test_forwards_dimensions_when_given(self) -> None:
        fake = _FakePostJson(EMBEDDING_RESPONSE)
        func = build_remote_embedding_func(BASE_SETTINGS, post_json=fake, signer=_fake_signer)

        _ = await func(model='gemini/gemini-embedding-001', input=['a'], dimensions=1024)

        assert fake.requests[0]['body']['dimensions'] == 1024

    async def test_omits_dimensions_when_not_given(self) -> None:
        fake = _FakePostJson(EMBEDDING_RESPONSE)
        func = build_remote_embedding_func(BASE_SETTINGS, post_json=fake, signer=_fake_signer)

        _ = await func(model='gemini/gemini-embedding-001', input=['a'])

        assert 'dimensions' not in fake.requests[0]['body']

    async def test_sends_master_key_header_when_configured(self) -> None:
        fake = _FakePostJson(EMBEDDING_RESPONSE)
        settings = {**BASE_SETTINGS, 'auth_token': 'master-key'}
        func = build_remote_embedding_func(settings, post_json=fake, signer=_fake_signer)

        _ = await func(model='gemini/gemini-embedding-001', input=['a'])

        assert fake.requests[0]['headers']['X-Gateway-Master-Key'] == 'master-key'

    async def test_transport_errors_propagate(self) -> None:
        func = build_remote_embedding_func(
            BASE_SETTINGS, post_json=_ExplodingPostJson(), signer=_fake_signer
        )

        with pytest.raises(RemoteGatewayError, match='HTTP 500'):
            _ = await func(model='gemini/gemini-embedding-001', input=['a'])

    def test_requires_base_url(self) -> None:
        with pytest.raises(ValueError, match='MODEL_GATEWAY_URL'):
            build_remote_embedding_func({})

    def test_requires_region_for_default_signer(self) -> None:
        with pytest.raises(ValueError, match='SigV4'):
            build_remote_embedding_func({'base_url': 'https://gw.example'})
