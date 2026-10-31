# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import json
import uuid
from typing import Any

import boto3  # type: ignore[import-untyped]

from ._sqs_queue_helpers import *


class _SqsQueueMisc:
    _client_cache: Any = None
    sqs_client: Any = None
    client: Any = None
    sfn_client: Any = None
    step_functions_client: Any = None
    ingestion_queue_url: Any = None
    reprocessing_queue_url: Any = None
    reports_queue_url: Any = None
    dead_letter_queue_url: Any = None
    concurrency_cap: int = 0
    max_receive_count: int = 0
    receive_count: int = 0
    state_machine_arn: Any = None
    workers: Any = None
    step_workers: Any = None
    handlers: Any = None
    config: Any = None
    queue_config: Any = None
    _sent: Any = None
    _dead_letters: Any = None
    _retry_list: Any = None
    _queue_state: Any = None
    _receive_counts: Any = None
    _inflight: Any = None
    _receipts: Any = None

    def _get_sqs_client(self) -> Any:
        if self._client_cache is not None:
            return self._client_cache
        if self.sqs_client is not None:
            self._client_cache = self.sqs_client
            return self.sqs_client
        try:
            client = boto3.client('sqs')
            self._client_cache = client
            self.sqs_client = client
            self.client = client
            return client
        except Exception:
            return None

    def _get_sfn_client(self) -> Any:
        if self.sfn_client is not None:
            return self.sfn_client
        client = self._get_sqs_client()
        if client is not None and hasattr(client, 'start_execution'):
            self.sfn_client = client
            self.step_functions_client = client
            return client
        try:
            client = boto3.client('stepfunctions')
            self.sfn_client = client
            self.step_functions_client = client
            return client
        except Exception:
            return None

    def _queue_url_for(self, queue: Any = None, **kwargs: Any) -> Any:
        if isinstance(queue, str) and queue:
            # allow symbolic names
            mapping = {
                'ingestion': self.ingestion_queue_url,
                'ingest': self.ingestion_queue_url,
                'reprocessing': self.reprocessing_queue_url,
                'reprocess': self.reprocessing_queue_url,
                'reports': self.reports_queue_url,
                'report': self.reports_queue_url,
                'dead_letter': self.dead_letter_queue_url,
                'dlq': self.dead_letter_queue_url,
                'default': self.ingestion_queue_url,
            }
            if queue in mapping:
                val = mapping.get(queue) or self.ingestion_queue_url
                return (
                    _coerce_str(val)
                    if val is not None
                    else self.ingestion_queue_url or 'https://sqs.test/ingest'
                )
            if queue.startswith('http') or '://' in queue or queue.endswith('queue'):
                return queue
            # maybe queue name provided with partial mapping
            for key, val in mapping.items():
                if queue.lower().startswith(key) and val:
                    return val
            return queue
        val = _first(kwargs, 'queue_url', 'queue', 'url', 'target_queue', default=None)
        if isinstance(val, str) and val:
            return self._queue_url_for(val)
        return (
            _coerce_str(self.ingestion_queue_url)
            if self.ingestion_queue_url is not None
            else 'https://sqs.test/ingest'
        )

    def _company_id(self, value: Any) -> str:
        if value is None:
            return ''
        return _coerce_str(value)

    def _encode(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload).decode('utf-8', 'replace')
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return str(payload)

    def _normalize_message(self, raw: Any, queue_url: str) -> dict[str, Any]:
        if isinstance(raw, dict):
            msg = dict(raw)
        else:
            msg = {'Body': _coerce_str(raw)}
        # ensure ids (stable across receives for count tracking)
        if 'MessageId' not in msg and 'message_id' not in msg and 'id' not in msg:
            stable = msg.get('ReceiptHandle') or msg.get('receipt_handle') or msg.get('receipt')
            if stable is None:
                body_val = msg.get('Body') or msg.get('body')
                stable = (
                    body_val
                    if not isinstance(body_val, (dict, list))
                    else json.dumps(body_val, sort_keys=True, default=str)
                )
            if stable is None:
                stable = str(uuid.uuid4())
            msg['MessageId'] = stable
        msg.setdefault('message_id', msg.get('MessageId') or msg.get('id'))
        msg.setdefault('id', msg.get('message_id'))
        msg.setdefault('ReceiptHandle', msg.get('receipt_handle') or str(uuid.uuid4()))
        msg.setdefault('receipt_handle', msg.get('ReceiptHandle'))
        # body
        if 'Body' not in msg and 'body' in msg:
            msg['Body'] = msg['body']
        if 'body' not in msg and 'Body' in msg:
            msg['body'] = msg['Body']
        # receive count
        rc = None
        attrs = msg.get('Attributes') or msg.get('attributes') or {}
        if isinstance(attrs, dict):
            rc = attrs.get('ApproximateReceiveCount') or attrs.get('ReceiveCount')
        rc = rc or msg.get('ReceiveCount') or msg.get('receive_count')
        try:
            msg['ReceiveCount'] = int(rc) if rc is not None else msg.get('ReceiveCount', 0)
        except (TypeError, ValueError):
            msg['ReceiveCount'] = msg.get('ReceiveCount', 0) or 0
        msg.setdefault('receive_count', msg['ReceiveCount'])
        msg.setdefault('QueueUrl', queue_url)
        msg.setdefault('queue_url', queue_url)
        # company id
        body = msg.get('Body')
        company = None
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    company = (
                        parsed.get('company_id')
                        or parsed.get('companyId')
                        or parsed.get('tenant_id')
                    )
            except Exception:
                pass
        if company is not None:
            msg.setdefault('company_id', _coerce_str(company))
        return msg

    def _track_receive_count(self, msg: dict[str, Any]) -> Any:
        key = _coerce_str(
            msg.get('message_id') or msg.get('MessageId') or msg.get('ReceiptHandle') or ''
        )
        cached = self._receive_counts.get(key)
        if cached is None:
            cached = 0
        cached += 1
        raw = msg.get('ReceiveCount') or msg.get('receive_count') or 0
        try:
            raw_int = int(raw)
            if raw_int > cached:
                cached = raw_int
        except (TypeError, ValueError):
            pass
        self._receive_counts[key] = cached
        msg['ReceiveCount'] = cached
        msg['receive_count'] = cached
        return cached

    # ------------------------------------------------------------------ send


async def _sqs_release(self: Any, *args: Any, **kwargs: Any) -> Any:
    await self.release_capacity(*args, **kwargs)
    return await self.nack(*args, **kwargs)


# capacity


def register_worker(self: Any, step: Any, handler: Any = None, **kwargs: Any) -> None:
    key = _coerce_str(step)
    if handler is None:
        handler = kwargs.get('handler') or kwargs.get('worker')
    self.workers[key] = handler
    self.step_workers[key] = handler
    self.handlers[key] = handler


def get_worker(self: Any, step: Any, company_id: Any = None) -> Any:
    return self.workers.get(_coerce_str(step))


async def invoke_worker(self: Any, *args: Any, **kwargs: Any) -> Any:
    step = _first(kwargs, 'step', 'name', 'worker', default=None)
    if step is None and args:
        step = args[0]
        args = args[1:]
    handler = self.workers.get(_coerce_str(step)) if step is not None else None
    if handler is None:
        return {'step': step, 'status': 'skipped'}
    if callable(handler):
        result = handler(*args, **kwargs)
        result = await _await_value(result)
        return result
    if hasattr(handler, 'handle'):
        result = handler.handle(*args, **kwargs)
        result = await _await_value(result)
        return result
    if hasattr(handler, 'run'):
        result = handler.run(*args, **kwargs)
        result = await _await_value(result)
        return result
    return handler


# Sync/async mixing is intentionally avoided: callers await send()/receive() directly.
