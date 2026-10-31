# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_receive(self: Any, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    kwargs = dict(kwargs)
    company_filter = _first(kwargs, 'company_id', 'company', 'tenant_id', 'tenant', default=None)
    queue_arg = _first(kwargs, 'queue', 'queue_name', 'queue_url', default=None)
    if (
        queue_arg is None
        and args
        and isinstance(args[0], str)
        and (
            '://' in args[0]
            or args[0] in {'ingestion', 'reports', 'reprocessing', 'dead_letter', 'dlq'}
        )
    ):
        queue_arg = args[0]
        args = args[1:]
    queue_url = self._queue_url_for(queue_arg, **kwargs)
    max_number = _first(
        kwargs, 'max_number_of_messages', 'max_messages', 'limit', 'batch_size', default=None
    )
    if max_number is None:
        max_number = self.batch_size
    try:
        max_number = int(max_number)
    except (TypeError, ValueError):
        max_number = self.batch_size
    wait_time = _first(kwargs, 'wait_time_seconds', 'wait_time', default=self.wait_time_seconds)
    visibility = _first(
        kwargs,
        'visibility_timeout',
        'visibility_timeout_seconds',
        default=self.visibility_timeout_seconds,
    )

    messages: list[dict[str, Any]] = []
    client = self._get_sqs_client()
    raw_messages: Any = []
    if client is not None and hasattr(client, 'receive_message'):
        params = {
            'QueueUrl': queue_url,
            'MaxNumberOfMessages': max_number,
            'WaitTimeSeconds': wait_time,
            'VisibilityTimeout': visibility,
        }
        # passthrough
        for passthrough in (
            'AttributeName',
            'AttributeNames',
            'MessageAttributeName',
            'MessageAttributeNames',
        ):
            if kwargs.get(passthrough) is not None:
                params[passthrough] = kwargs.get(passthrough)
        try:
            response = client.receive_message(**params)
            response = await _await_value(response)
        except TypeError:
            try:
                response = client.receive_message(queue_url, max_number)
                response = await _await_value(response)
            except Exception:
                response = None
        except Exception:
            response = None
        if isinstance(response, dict):
            raw_messages = (
                response.get('Messages')
                or response.get('messages')
                or response.get('message')
                and [response.get('message')]
            )
        elif isinstance(response, list):
            raw_messages = response
        # if client is a fake returning a single dict at top-level
        if not raw_messages and isinstance(response, dict):
            for key in ('Message', 'Body', 'body'):
                if key in response:
                    raw_messages = [response]
                    break
    elif client is not None and hasattr(client, 'receive'):
        try:
            response = client.receive(queue_url, max_number, **kwargs)
            response = await _await_value(response)
            if isinstance(response, list):
                raw_messages = response
            elif isinstance(response, dict):
                raw_messages = response.get('Messages') or [response]
        except Exception:
            raw_messages = []

    # fall back to internal queue
    if not raw_messages:
        internal = self._queue_state.setdefault(queue_url, [])
        while internal and len(raw_messages) < max_number:
            raw_messages.append(internal.pop(0))

    for raw in raw_messages:
        msg = self._normalize_message(raw, queue_url)
        receive_count = self._track_receive_count(msg)
        # dead-letter threshold
        if receive_count >= self.max_receive_count:
            key = _coerce_str(
                msg.get('message_id') or msg.get('MessageId') or msg.get('ReceiptHandle') or ''
            )
            if not hasattr(self, '_dead_lettered_keys'):
                self._dead_lettered_keys = set()
            if key not in self._dead_lettered_keys:
                self._dead_lettered_keys.add(key)
                self._dead_letters.append(msg)
                if msg not in self._retry_list:
                    self._retry_list.append(msg)
            # send to dlq client best-effort
            if client is not None and hasattr(client, 'send_message'):
                try:
                    client.send_message(
                        QueueUrl=self.dead_letter_queue_url, MessageBody=self._encode(msg)
                    )
                except Exception:
                    pass
            company = msg.get('company_id')
            if company is not None:
                cid = self._company_id(company)
                if cid and self._inflight.get(cid, 0) > 0:
                    self._inflight[cid] -= 1
            continue
        # company filter
        if company_filter is not None:
            msg_company = msg.get('company_id') or ''
            if msg_company and _coerce_str(company_filter) != msg_company:
                # requeue and skip
                self._queue_state.setdefault(queue_url, []).append(
                    raw if isinstance(raw, dict) else msg
                )
                continue
        # store receipt for ack
        receipt_key = _coerce_str(msg.get('ReceiptHandle') or msg.get('receipt_handle') or '')
        self._receipts[receipt_key] = msg
        messages.append(msg)

    return messages


# aliases for receive
