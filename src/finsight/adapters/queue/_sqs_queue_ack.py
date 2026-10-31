# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_ack(self: Any, *args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    receipt = _first(kwargs, 'receipt_handle', 'ReceiptHandle', 'handle', 'id', default=None)
    if receipt is None and args:
        first = args[0]
        if isinstance(first, dict):
            receipt = (
                first.get('ReceiptHandle')
                or first.get('receipt_handle')
                or first.get('receipt')
                or first.get('handle')
            )
            args = args[1:]
        else:
            receipt = first
            args = args[1:]
    message = None
    if isinstance(receipt, dict):
        message = receipt
        receipt = (
            message.get('ReceiptHandle')
            or message.get('receipt_handle')
            or message.get('handle')
            or message.get('id')
        )
    # company
    company_id = _first(kwargs, 'company_id', 'company', default=None)
    if company_id is None and args:
        company_id = args[0]
    queue_url = self._queue_url_for(_first(kwargs, 'queue', 'queue_url', default=None), **kwargs)

    client = self._get_sqs_client()
    if client is not None and hasattr(client, 'delete_message'):
        params = {'QueueUrl': queue_url, 'ReceiptHandle': _coerce_str(receipt)}
        try:
            res = client.delete_message(**params)
            res = await _await_value(res)
        except TypeError:
            try:
                res = client.delete_message(queue_url, _coerce_str(receipt))
                res = await _await_value(res)
            except Exception:
                res = None
        except Exception:
            res = None
    else:
        res = True
    # release concurrency slot
    msg = self._receipts.pop(_coerce_str(receipt), None)
    company = company_id or (msg.get('company_id') if isinstance(msg, dict) else None)
    if company is not None and self._inflight.get(self._company_id(company), 0) > 0:
        self._inflight[self._company_id(company)] -= 1
    return True if res is None else res


# aliases ack
