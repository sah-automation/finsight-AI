"""Tests for the remote model-gateway chat transport (issue #330).

The remote transport plugs into the existing ``completion_func`` seam of
``LiteLLMGateway``: it receives litellm-shaped kwargs and must return an async
iterable of litellm-shaped dict chunks, so the app-side fallback, metering,
first-token, and extraction logic stay untouched. The HTTP layer is injectable
(``post_stream``/``signer``) so these tests never touch the network.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from finsight.adapters.llm.remote_gateway import (
    RemoteGatewayError,
    _sigv4_sign,
    build_remote_completion_func,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from botocore.credentials import Credentials

BASE_SETTINGS = {'base_url': 'https://gw.lambda-url.us-east-1.on.aws', 'region': 'us-east-1'}


class _FakePostStream:
    """Post-stream double: records the request, yields NDJSON lines."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.requests: list[dict[str, Any]] = []

    async def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
    ) -> AsyncIterator[str]:
        self.requests.append(
            {
                'url': url,
                'headers': dict(headers),
                'body': json.loads(body),
                'timeout': timeout_seconds,
            }
        )
        for line in self.lines:
            yield line


class _ExplodingPostStream:
    """Post-stream double that mimics a gateway 5xx."""

    async def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
    ) -> AsyncIterator[str]:
        raise RemoteGatewayError(f'gateway POST {url} failed: HTTP 502')
        yield ''  # pragma: no cover — makes this an async generator


CHAT_KWARGS: dict[str, Any] = {
    'model': 'groq/openai/gpt-oss-120b',
    'messages': [{'role': 'user', 'content': 'hello'}],
    'stream': True,
    'max_tokens': 1000,
    'temperature': 0.7,
    'timeout': 20,
}

CHUNKS: list[dict[str, Any]] = [
    {'choices': [{'delta': {'content': 'Hel'}}], 'model': 'groq/openai/gpt-oss-120b'},
    {
        'choices': [{'delta': {'content': 'lo'}}],
        'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5},
    },
]


def _ndjson(chunks: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(chunk) for chunk in chunks]


@pytest.mark.unit
class TestRemoteCompletionTransport:
    """The chat transport adapts the gateway HTTP API to litellm-shaped chunks."""

    async def test_yields_litellm_shaped_chunks(self) -> None:
        fake = _FakePostStream(_ndjson(CHUNKS))
        func = build_remote_completion_func(BASE_SETTINGS, post_stream=fake)

        yielded = [chunk async for chunk in func(**CHAT_KWARGS)]

        assert yielded == CHUNKS
        request = fake.requests[0]
        assert request['url'] == 'https://gw.lambda-url.us-east-1.on.aws/v1/chat/completions'
        assert request['body']['model'] == 'groq/openai/gpt-oss-120b'
        assert request['body']['messages'] == CHAT_KWARGS['messages']
        assert request['body']['stream'] is True
        assert request['timeout'] == 20

    async def test_blank_lines_are_skipped(self) -> None:
        fake = _FakePostStream(['', *_ndjson(CHUNKS), '', ''])
        func = build_remote_completion_func(BASE_SETTINGS, post_stream=fake)

        yielded = [chunk async for chunk in func(**CHAT_KWARGS)]

        assert yielded == CHUNKS

    async def test_sends_master_key_header_when_configured(self) -> None:
        fake = _FakePostStream(_ndjson(CHUNKS))
        settings = {**BASE_SETTINGS, 'auth_token': 'master-key'}
        func = build_remote_completion_func(settings, post_stream=fake)

        _ = [chunk async for chunk in func(**CHAT_KWARGS)]

        headers = fake.requests[0]['headers']
        assert headers['X-Gateway-Master-Key'] == 'master-key'

    async def test_omits_master_key_without_token_or_signer(self) -> None:
        fake = _FakePostStream(_ndjson(CHUNKS))
        func = build_remote_completion_func(BASE_SETTINGS, post_stream=fake)

        _ = [chunk async for chunk in func(**CHAT_KWARGS)]

        assert 'X-Gateway-Master-Key' not in fake.requests[0]['headers']

    async def test_applies_injected_signer(self) -> None:
        fake = _FakePostStream(_ndjson(CHUNKS))

        def signer(method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
            return {**headers, 'X-Sigv4': 'signed'}

        func = build_remote_completion_func(BASE_SETTINGS, post_stream=fake, signer=signer)

        _ = [chunk async for chunk in func(**CHAT_KWARGS)]

        assert fake.requests[0]['headers']['X-Sigv4'] == 'signed'

    async def test_transport_errors_propagate(self) -> None:
        func = build_remote_completion_func(BASE_SETTINGS, post_stream=_ExplodingPostStream())

        with pytest.raises(RemoteGatewayError, match='HTTP 502'):
            _ = [chunk async for chunk in func(**CHAT_KWARGS)]

    def test_requires_base_url(self) -> None:
        with pytest.raises(ValueError, match='MODEL_GATEWAY_URL'):
            build_remote_completion_func({})

    def test_requires_region_for_default_signer(self) -> None:
        with pytest.raises(ValueError, match='SigV4'):
            build_remote_completion_func({'base_url': 'https://gw.example'})

    async def test_default_signer_is_sigv4_when_region_present(self) -> None:
        """With a region and no injected signer the request is SigV4-signed."""
        captured: dict[str, Any] = {}

        def fake_post_stream(
            url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
        ) -> AsyncIterator[str]:
            captured['headers'] = dict(headers)
            return _FakePostStream(_ndjson(CHUNKS))(url, headers, body, timeout_seconds)

        func = build_remote_completion_func(BASE_SETTINGS, post_stream=fake_post_stream)
        _ = [chunk async for chunk in func(**CHAT_KWARGS)]

        assert captured['headers']['Authorization'].startswith('AWS4-HMAC-SHA256')


@pytest.mark.unit
class TestSigv4Signer:
    """The default signer produces AWS SigV4 headers for the lambda service."""

    def test_produces_sigv4_authorization(self) -> None:
        headers = _sigv4_sign(
            'POST',
            'https://gw.lambda-url.us-east-1.on.aws/v1/chat/completions',
            {'Content-Type': 'application/json'},
            b'{}',
            region='us-east-1',
            credentials=Credentials('AKIDEXAMPLE', 'secret'),
        )

        assert headers['Authorization'].startswith('AWS4-HMAC-SHA256')
        assert 'X-Amz-Date' in headers
        assert headers['X-Amz-Content-Sha256']
