"""Contract tests for the public Q&A ask API and typed SSE streaming."""

from __future__ import annotations

import asyncio
from typing import Never

from finsight.domain.entities.insufficient_data import InsufficientData
from finsight.entrypoints.api.ask import _handle


async def _collect(response: object) -> str:
    body = b''
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()
    return body.decode('utf-8')


def test_ask_streams_typed_sse_events_end_to_end() -> None:
    class FakeAsk:
        async def run(self, context: object, question: object) -> object:
            return {
                'answer': 'Margins fell because costs rose.',
                'citations': [{'document': 'q3.pdf', 'page': 4}],
                'model': 'primary-model',
                'cached': False,
            }

    async def run() -> str:
        response = await _handle(
            {'question': 'Why did margins fall?', 'company_id': 'company-1', 'use_case': FakeAsk()}
        )
        return await _collect(response)

    text = asyncio.run(run())
    assert 'event: status' in text
    assert 'event: delta' in text
    assert 'event: citation' in text
    assert 'event: complete' in text
    assert 'Margins fell because costs rose.' in text
    assert '"model": "primary-model"' in text


def test_ask_streams_insufficient_data_without_sentence() -> None:
    class FakeAsk:
        async def run(self, context: object, question: object) -> object:
            return InsufficientData(
                reason='no relevant documents',
                company_id='company-1',
                question=question,
            )

    async def run() -> str:
        response = await _handle(
            {'question': 'Unknown?', 'company_id': 'company-1', 'use_case': FakeAsk()}
        )
        return await _collect(response)

    text = asyncio.run(run())
    assert 'event: insufficient_data' in text
    assert 'no relevant documents' in text
    assert 'event: delta' not in text


def test_ask_maps_busy_errors_to_friendly_message() -> None:
    class FakeAsk:
        async def run(self, context, question) -> Never:
            raise TimeoutError('provider raw timeout')

    async def run() -> str:
        response = await _handle(
            {'question': 'Why?', 'company_id': 'company-1', 'use_case': FakeAsk()}
        )
        return await _collect(response)

    text = asyncio.run(run())
    assert 'The system is busy right now. Please try again in a moment.' in text
    assert 'provider raw timeout' not in text
    assert 'TimeoutError' not in text


def test_ask_does_not_leak_sensitive_document_text() -> None:
    raw_error_text = 'raw backend explosion details'

    class FakeAsk:
        async def run(self, context, question) -> Never:
            raise RuntimeError(raw_error_text)

    async def run() -> str:
        response = await _handle(
            {'question': 'Why?', 'company_id': 'company-1', 'use_case': FakeAsk()}
        )
        return await _collect(response)

    text = asyncio.run(run())
    assert raw_error_text not in text
    assert 'event: error' in text
