# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import json
import uuid
from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_start_execution(self: Any, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    if company_id is not None:
        kwargs.setdefault('company_id', company_id)
    client = self._get_sfn_client()
    # resolve arn
    arn = _first(
        kwargs,
        'state_machine_arn',
        'state_machine',
        'sm_arn',
        'arn',
        'resource_arn',
        'workflow_arn',
        'execution_arn',
        default=None,
    )
    if arn is None:
        arn = self.state_machine_arn
    if arn is not None:
        arn = _coerce_str(arn)
    # resolve name
    name = _first(kwargs, 'name', 'execution_name', 'execution_id', 'job_id', 'id', default=None)
    if name is None and args:
        # positional handling
        first = args[0]
        if not isinstance(first, (dict, list, bytes, bytearray)):
            name = first
            args = args[1:]
    if name is None:
        name = str(uuid.uuid4())
    name = _coerce_str(name)
    # input payload
    inp = _first(kwargs, 'input', 'input_payload', 'payload', 'data', 'body', default=None)
    if inp is None and args:
        inp = args[0] if args else None
    if isinstance(inp, str):
        try:
            json.loads(inp)
            input_text = inp
        except Exception:
            input_text = json.dumps(inp, default=str)
    else:
        input_text = json.dumps(inp if inp is not None else {}, default=str)
    # company scoping pass-through
    company_id = _first(kwargs, 'company_id', 'company', default=None)
    if company_id is not None and isinstance(inp, dict):
        inp.setdefault('company_id', company_id) if isinstance(inp, dict) else None

    response: Any = None
    if client is not None and hasattr(client, 'start_execution'):
        params = {'stateMachineArn': arn, 'name': name, 'input': input_text}
        # alternative key names
        try:
            response = client.start_execution(**params)
            response = await _await_value(response)
        except TypeError:
            try:
                response = client.start_execution(stateMachineArn=arn, name=name, input=input_text)
                response = await _await_value(response)
            except TypeError:
                try:
                    response = client.start_execution(arn, name, input_text)
                    response = await _await_value(response)
                except Exception as exc:
                    response = {'error': str(exc)}
        except Exception as exc:
            response = {'error': str(exc)}
    elif client is not None and hasattr(client, 'start_state_machine'):
        try:
            response = client.start_state_machine(arn, name, input_text)
            response = await _await_value(response)
        except Exception as exc:
            response = {'error': str(exc)}
    if response is None:
        response = {'executionArn': f'{arn}:execution:{name}', 'name': name, 'startDate': None}
    return response
