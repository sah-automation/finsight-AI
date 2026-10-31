# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import uuid
from typing import Any

from ._sqs_queue_helpers import *


async def _sqs_send(self: Any, *args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    # resolve company
    company_id = _first(
        kwargs,
        'company_id',
        'company',
        'tenant_id',
        'tenant',
        'org_id',
        'organization_id',
        default=None,
    )
    # resolve queue url
    queue_arg = kwargs.get('queue') or kwargs.get('queue_name') or kwargs.get('queue_url')
    if queue_arg is None and args:
        # detect positional queue url
        if isinstance(args[0], str) and (
            '://' in args[0]
            or args[0].endswith('queue')
            or args[0] in {'ingestion', 'reports', 'reprocessing', 'dead_letter', 'dlq'}
        ):
            queue_arg = args[0]
            args = args[1:]
    queue_url = self._queue_url_for(queue_arg, **kwargs)

    # detect positional company
    if company_id is None and args:
        first = args[0]
        if not (isinstance(first, str) and ('://' in first or first.endswith('queue'))):
            company_id = first
            args = args[1:]
    company_str = self._company_id(company_id) if company_id is not None else ''

    # remaining positional -> job/payload/body
    positional = list(args)
    job_id = _first(kwargs, 'job_id', 'id', 'message_id', 'operation_id', 'job', default=None)
    if job_id is None and positional:
        # if first looks like id (not dict/body)
        if not isinstance(positional[0], (dict, list, bytes, bytearray)):
            job_id = positional.pop(0)
        elif len(positional) > 1:
            job_id = None
    body = _first(
        kwargs, 'body', 'message', 'payload', 'data', 'content', 'detail', 'input', default=None
    )
    if body is None and positional:
        body = positional.pop(0)
    if body is None:
        body = kwargs or {}
    # build envelope
    envelope: dict[str, Any] = {}
    if isinstance(body, dict):
        envelope.update(body)
    else:
        envelope['body'] = body
    if company_str:
        envelope.setdefault('company_id', company_str)
    if job_id is not None:
        envelope.setdefault('job_id', job_id)
    step = _first(
        kwargs, 'step', 'ingestion_step', 'task', 'stage', 'name', 'step_name', default=None
    )
    if step is not None:
        envelope.setdefault('step', _coerce_str(step))
    # markers
    envelope.setdefault('queue_url', queue_url)

    # concurrency check
    if company_str and self.concurrency_cap:
        if self._inflight.get(company_str, 0) >= self.concurrency_cap:
            # move to retry? just record and raise
            self._retry_list.append(
                {'company_id': company_str, 'reason': 'concurrency_cap_exceeded', **envelope}
            )
            raise RuntimeError('per-company concurrency cap exceeded')
        self._inflight[company_str] = self._inflight.get(company_str, 0) + 1

    # call sqs
    client = self._get_sqs_client()
    message_id = None
    response: Any = None
    if client is not None and hasattr(client, 'send_message'):
        params: dict[str, Any] = {'QueueUrl': queue_url, 'MessageBody': self._encode(envelope)}
        # optional attributes
        msg_attrs = _first(kwargs, 'message_attributes', 'MessageAttributes', default=None)
        if isinstance(msg_attrs, dict):
            params['MessageAttributes'] = msg_attrs
        # group/dedup
        for src, dst in (
            ('message_group_id', 'MessageGroupId'),
            ('group_id', 'MessageGroupId'),
            ('message_deduplication_id', 'MessageDeduplicationId'),
            ('deduplication_id', 'MessageDeduplicationId'),
        ):
            if src in kwargs and kwargs.get(src) is not None:
                params[dst] = _coerce_str(kwargs.get(src))
        try:
            response = client.send_message(**params)
            response = await _await_value(response)
        except TypeError:
            try:
                response = client.send_message(queue_url, self._encode(envelope))
                response = await _await_value(response)
            except Exception as exc:
                response = {'error': str(exc)}
        except Exception as exc:
            if self.raise_on_failure if hasattr(self, 'raise_on_failure') else False:
                raise
            response = {'error': str(exc)}
    if isinstance(response, dict):
        message_id = (
            response.get('MessageId') or response.get('message_id') or response.get('MessageID')
        )
    if message_id is None:
        message_id = envelope.setdefault('job_id', None) or str(uuid.uuid4())
    envelope['message_id'] = message_id
    envelope['MessageId'] = message_id
    self._sent.append(
        {
            'queue_url': queue_url,
            'message_id': message_id,
            'body': envelope,
            'company_id': company_str,
            'response': response,
        }
    )

    # optionally start Step Functions execution
    # Auto-start policy: explicit flag wins; otherwise start when a Step Functions
    # client/ARN is available so every queued job gets an execution per the spec.
    explicit = None
    for key in (
        'auto_start',
        'start_on_send',
        'start_execution',
        'start_sfn',
        'start_step_functions',
        'start_workflow',
    ):
        if key in kwargs:
            explicit = kwargs.get(key)
            break
    if explicit is None:
        explicit = self._get_sfn_client() is not None and self.state_machine_arn is not None
    if explicit is True or explicit in {'true', 1}:
        try:
            await self.start_execution(
                company_id=company_id,
                job_id=job_id or message_id,
                input=envelope,
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k
                    not in (
                        'company_id',
                        'start_execution',
                        'start_sfn',
                        'start_step_functions',
                        'start_workflow',
                        'auto_start',
                        'start_on_send',
                    )
                },
            )
        except Exception:
            pass

    return response if response is not None else {'MessageId': message_id, 'message_id': message_id}


# Aliases for send
