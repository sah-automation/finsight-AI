"""Ingestion worker resilience for missing resources (issue #259)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))

import run_ingestion_worker as worker  # type: ignore[import-not-found]

from finsight.core.errors import (
    DocumentVersionNotFoundError,
    SourceObjectNotFoundError,
)

pytestmark = pytest.mark.unit


class _Queue:
    def __init__(self) -> None:
        self.acked: list[object] = []
        self.nacked: list[object] = []
        self.dead_lettered: list[object] = []

    async def ack(self, message: object) -> None:
        self.acked.append(message)

    async def nack(self, message: object) -> None:
        self.nacked.append(message)

    async def dead_letter(self, message: object) -> None:
        self.dead_lettered.append(message)


class _Pipeline:
    def __init__(self, error: Exception | None = None, result: dict | None = None) -> None:
        self._error = error
        self._result = result if result is not None else {'status': 'completed'}

    async def run_pipeline(self, context: object) -> dict:
        if self._error is not None:
            raise self._error
        return self._result


def _message(receive_count: int = 1) -> dict:
    return {
        'company_id': 'company-a',
        'document_id': 'document-1',
        'version_id': 'version-1',
        'key': 'company-a/documents/document-1/versions/version-1/report.pdf',
        'ReceiveCount': receive_count,
    }


async def test_process_message_handles_document_version_not_found(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv('INGESTION_MAX_RETRIES', raising=False)
    monkeypatch.delenv('INGESTION_DLQ_ON_MAX_RETRIES', raising=False)
    queue = _Queue()
    pipeline = _Pipeline(error=DocumentVersionNotFoundError('version missing'))

    with caplog.at_level(logging.WARNING, logger='finsight.ingestion_worker'):
        await worker.process_message(queue, pipeline, _message(receive_count=1))

    assert queue.nacked, 'expected nack on missing document version'
    assert not queue.dead_lettered
    assert not queue.acked
    assert any(r.levelname == 'WARNING' for r in caplog.records)


async def test_process_message_handles_source_object_not_found(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv('INGESTION_MAX_RETRIES', raising=False)
    monkeypatch.delenv('INGESTION_DLQ_ON_MAX_RETRIES', raising=False)
    queue = _Queue()
    pipeline = _Pipeline(error=SourceObjectNotFoundError('object missing'))

    with caplog.at_level(logging.WARNING, logger='finsight.ingestion_worker'):
        await worker.process_message(queue, pipeline, _message(receive_count=1))

    assert queue.nacked
    assert not queue.dead_lettered
    assert not queue.acked
    assert any(r.levelname == 'WARNING' for r in caplog.records)


async def test_process_message_dead_letters_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('INGESTION_MAX_RETRIES', '3')
    monkeypatch.setenv('INGESTION_DLQ_ON_MAX_RETRIES', 'true')
    queue = _Queue()
    pipeline = _Pipeline(error=DocumentVersionNotFoundError('version missing'))

    await worker.process_message(queue, pipeline, _message(receive_count=3))

    assert queue.dead_lettered, 'expected dead_letter after max retries'
    assert not queue.nacked
    assert not queue.acked


async def test_process_message_nacks_before_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('INGESTION_MAX_RETRIES', '3')
    monkeypatch.setenv('INGESTION_DLQ_ON_MAX_RETRIES', 'true')
    queue = _Queue()
    pipeline = _Pipeline(error=SourceObjectNotFoundError('object missing'))

    await worker.process_message(queue, pipeline, _message(receive_count=2))

    assert queue.nacked
    assert not queue.dead_lettered


async def test_process_message_respects_dlq_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('INGESTION_MAX_RETRIES', '3')
    monkeypatch.setenv('INGESTION_DLQ_ON_MAX_RETRIES', 'false')
    queue = _Queue()
    pipeline = _Pipeline(error=DocumentVersionNotFoundError('version missing'))

    await worker.process_message(queue, pipeline, _message(receive_count=5))

    assert queue.nacked
    assert not queue.dead_lettered


async def test_process_message_valid_message_still_acks() -> None:
    queue = _Queue()
    pipeline = _Pipeline(result={'status': 'completed'})

    result = await worker.process_message(queue, pipeline, _message())

    assert queue.acked
    assert not queue.nacked
    assert not queue.dead_lettered
    assert isinstance(result, dict)


async def test_process_message_unexpected_error_propagates() -> None:
    queue = _Queue()
    pipeline = _Pipeline(error=ValueError('boom'))

    with pytest.raises(ValueError):
        await worker.process_message(queue, pipeline, _message())

    assert queue.nacked
    assert not queue.dead_lettered
    assert not queue.acked
