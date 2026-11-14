# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_nack(self: Any, *args: Any, **kwargs: Any) -> Any:
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
                or first.get('id')
            )
            args = args[1:]
        else:
            receipt = first
            args = args[1:]
    # requeue by visibility change or send back
    queue_url = self._queue_url_for(_first(kwargs, 'queue', 'queue_url', default=None), **kwargs)
    client = self._get_sqs_client()
    if client is not None and hasattr(client, 'change_message_visibility'):
        try:
            client.change_message_visibility(
                QueueUrl=queue_url, ReceiptHandle=_coerce_str(receipt), VisibilityTimeout=0
            )
        except Exception:
            pass
    # track retry
    self._retry_list.append({'receipt_handle': receipt, 'reason': 'nack', 'queue_url': queue_url})
    return True
