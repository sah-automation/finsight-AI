"""Behavioral tests for embedding retry decorator."""

from __future__ import annotations

import asyncio
import logging

import pytest

from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding


class _ExplodingEmbedding:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error if error is not None else RuntimeError('provider down')
        self.calls: list[int] = []

    async def embed(self, *args: object, **kwargs: object) -> object:
        self.calls.append(len(self.calls))
        raise self.error


def test_retries_exhausted_warning_carries_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The exhaustion warning must name the alert and attach the caught exception."""
    inner = _ExplodingEmbedding()
    outer = RetryingEmbedding(inner, retries=2, retry_delay=0)

    with (
        caplog.at_level(logging.WARNING, logger='finsight.adapters.embedding.retrying_embedding'),
        pytest.raises(RuntimeError, match='provider down'),
    ):
        asyncio.run(outer.embed('co1', text='why did margins fall?'))

    records = [r for r in caplog.records if 'embedding retries exceeded' in r.message]
    assert records
    assert all(r.exc_info is not None for r in records)


def test_retries_exhausted_warning_alert_extras_preserved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The alert extras consumed by observability must survive the log enrichment."""
    outer = RetryingEmbedding(_ExplodingEmbedding(), retries=1, retry_delay=0)

    with (
        caplog.at_level(logging.WARNING, logger='finsight.adapters.embedding.retrying_embedding'),
        pytest.raises(RuntimeError),
    ):
        asyncio.run(outer.embed('co1', text='why did margins fall?'))

    records = [r for r in caplog.records if 'embedding retries exceeded' in r.message]
    assert records
    alert = [r for r in records if getattr(r, 'alert', None) == 'embedding_retries_exceeded']
    assert alert == records


def test_retry_decorator_reraises_last_exception() -> None:
    """After exhausting retries the original provider exception must propagate."""
    outer = RetryingEmbedding(_ExplodingEmbedding(), retries=1, retry_delay=0)

    with pytest.raises(RuntimeError, match='provider down'):
        asyncio.run(outer.embed('co1', text='why did margins fall?'))


def test_retry_decorator_success_passes_through() -> None:
    """A healthy provider must still be reached through the decorator."""

    class _Embedding:
        async def embed(self, *args: object, **kwargs: object) -> object:
            return [0.1, 0.2]

    outer = RetryingEmbedding(_Embedding(), retries=2, retry_delay=0)
    assert asyncio.run(outer.embed('co1', text='why did margins fall?')) == [0.1, 0.2]
