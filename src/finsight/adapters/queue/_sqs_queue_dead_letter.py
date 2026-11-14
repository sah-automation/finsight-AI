# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_dead_letter(self: Any, *args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    message = _first(kwargs, 'message', 'msg', default=None)
    if message is None and args:
        message = args[0]
        args = args[1:]
    # normalize
    if isinstance(message, dict):
        payload = message
    else:
        payload = {'body': message}
    queue_url = self._queue_url_for(_first(kwargs, 'queue', 'queue_url', default=None), **kwargs)
    client = self._get_sqs_client()
    if client is not None and hasattr(client, 'send_message'):
        try:
            client.send_message(
                QueueUrl=self.dead_letter_queue_url, MessageBody=self._encode(payload)
            )
        except Exception:
            pass
    if payload not in self._dead_letters:
        self._dead_letters.append(payload)
    if payload not in self._retry_list:
        self._retry_list.append(payload)
    # release slot
    company = payload.get('company_id') if isinstance(payload, dict) else None
    if company is not None:
        cid = self._company_id(company)
        if self._inflight.get(cid, 0) > 0:
            self._inflight[cid] -= 1
    return True
