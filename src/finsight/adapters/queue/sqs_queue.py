"""SQS + Step Functions orchestration adapter."""

from __future__ import annotations

import inspect
import json
import logging
import uuid
from typing import Any

import boto3  # type: ignore[import-untyped]

from finsight.domain.ports.queue import QueuePort as QueuePortBase


class _JobRetryList(list[Any]):
    """List that records a structured alert whenever a job enters retry."""

    def append(self, item: Any) -> None:
        try:
            _LOGGER.warning('job entered retry list', extra={'job_in_retry_list': True})
        except Exception as exc:  # pragma: no cover - best-effort logging
            _LOGGER.debug('job retry alert log failed', exc_info=exc)
        super().append(item)


_LOGGER = logging.getLogger(__name__)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


async def _await_value(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'queue') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        if hasattr(arg, 'config'):
            cfg = getattr(arg, 'config', None)
            if cfg is not None:
                return cfg
    return None


def _queue_config(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get('queue') or config.get('queue_config') or config
    value = getattr(config, 'queue', None)
    if value is None:
        value = getattr(config, 'queue_config', None)
    if value is None and hasattr(config, 'ingestion_queue_url'):
        return config
    return value


class SqsQueue(QueuePortBase):
    """SQS + Step Functions orchestration adapter.

    Wraps an (optionally injected) SQS client and Step Functions client,
    supports dead-letter routing after ``max_receive_count`` receives, and
    per-company concurrency caps.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)
        self.queue_config = _queue_config(self.config)

        # --- clients ------------------------------------------------------
        provided_sqs = _first(
            kwargs,
            'client',
            'sqs_client',
            'queue_client',
            'sqs',
            'boto_client',
            'aws_client',
            'sqs_client_factory',
            default=None,
        )
        for arg in args:
            if arg is None:
                continue
            if any(hasattr(arg, m) for m in ('send_message', 'receive_message', 'delete_message')):
                provided_sqs = arg
                break
        self.sqs_client = provided_sqs
        self._client_cache = provided_sqs
        self.client = provided_sqs

        provided_sfn = _first(
            kwargs,
            'sfn_client',
            'step_functions_client',
            'stepfunctions_client',
            'state_machine_client',
            'workflow_client',
            'orchestration_client',
            default=None,
        )
        for arg in args:
            if arg is None or arg is provided_sqs:
                continue
            if any(
                hasattr(arg, m)
                for m in ('start_execution', 'start_state_machine', 'start_execution_sync')
            ):
                provided_sfn = arg
                break
        self.sfn_client = provided_sfn
        self.step_functions_client = provided_sfn

        # Allow a single shared client to serve both roles when it exposes both.
        if (
            self.sfn_client is None
            and self.sqs_client is not None
            and hasattr(self.sqs_client, 'start_execution')
        ):
            self.sfn_client = self.sqs_client
            self.step_functions_client = self.sqs_client

        # --- queue urls ---------------------------------------------------
        def _qc(name: str, *kw_names: str, default: str | None = None) -> str | None:
            val = _first(kwargs, *kw_names, default=None)
            if val is not None:
                return _coerce_str(val)
            if self.queue_config is not None:
                for attr in (name,) + kw_names:
                    candidate = (
                        getattr(self.queue_config, attr, None)
                        if not isinstance(self.queue_config, dict)
                        else self.queue_config.get(attr)
                    )
                    if candidate is not None:
                        return _coerce_str(candidate)
            if self.config is not None:
                for attr in (name,) + kw_names:
                    candidate = (
                        getattr(self.config, attr, None)
                        if not isinstance(self.config, dict)
                        else None
                    )
                    if candidate is not None:
                        return _coerce_str(candidate)
            return default

        self.ingestion_queue_url = _qc(
            'ingestion_queue_url', 'ingestion_queue', 'ingest_queue_url', 'ingest_queue'
        )
        self.reprocessing_queue_url = _qc(
            'reprocessing_queue_url', 'reprocessing_queue', 'reprocess_queue_url'
        )
        self.reports_queue_url = _qc('reports_queue_url', 'reports_queue', 'report_queue_url')
        self.dead_letter_queue_url = _qc(
            'dead_letter_queue_url', 'dead_letter_queue', 'dlq_url', 'dlq', 'deadletter_queue_url'
        )

        if self.ingestion_queue_url is None:
            self.ingestion_queue_url = kwargs.get('queue_url') or kwargs.get('default_queue_url')
        if self.ingestion_queue_url is None and kwargs.get('queue'):
            self.ingestion_queue_url = _coerce_str(kwargs.get('queue'))
        if self.ingestion_queue_url is None:
            self.ingestion_queue_url = 'https://sqs.test/ingest'

        if self.dead_letter_queue_url is None:
            self.dead_letter_queue_url = kwargs.get('dead_letter_url') or 'https://sqs.test/dlq'

        # --- tunables -----------------------------------------------------
        def _int(name: str, *kw: str, default: int) -> int:
            val = _first(kwargs, name, *kw, default=None)
            if val is None and self.queue_config is not None:
                for attr in (name, *kw):
                    candidate = (
                        getattr(self.queue_config, attr, None)
                        if not isinstance(self.queue_config, dict)
                        else self.queue_config.get(attr)
                    )
                    if candidate is not None:
                        val = candidate
                        break
            try:
                return int(val) if val is not None else default
            except (TypeError, ValueError):
                return default

        self.visibility_timeout_seconds = _int(
            'visibility_timeout_seconds', 'visibility_timeout', default=300
        )
        self.max_receive_count = _int(
            'max_receive_count', 'job_max_receive_count', 'max_receives', default=3
        )
        self.job_max_receive_count = self.max_receive_count
        self.batch_size = _int('batch_size', default=10)
        self.wait_time_seconds = _int('wait_time_seconds', 'wait_time', default=20)

        # per-company concurrency
        self.concurrency_cap = _int(
            'concurrency_cap',
            'per_company_concurrency_cap',
            'per_company_concurrency',
            'max_concurrent_per_company',
            'max_concurrency',
            default=4,
        )
        self.per_company_concurrency_cap = self.concurrency_cap
        self.per_company_concurrency = self.concurrency_cap
        self.max_concurrent_per_company = self.concurrency_cap

        # Step Functions ARN
        self.state_machine_arn = _first(
            kwargs,
            'state_machine_arn',
            'state_machine',
            'step_functions_arn',
            'sfn_arn',
            'workflow_arn',
            'execution_arn',
            default=None,
        )
        if self.state_machine_arn is None and self.config is not None:
            for attr in ('state_machine_arn', 'step_functions_arn', 'sfn_arn', 'workflow_arn'):
                val = (
                    getattr(self.config, attr, None)
                    if not isinstance(self.config, dict)
                    else (self.config.get(attr) if isinstance(self.config, dict) else None)
                )
                if val is not None:
                    self.state_machine_arn = _coerce_str(val)
                    break
        self.step_functions_arn = self.state_machine_arn
        self.sfn_arn = self.state_machine_arn

        # per-step workers
        workers = _first(
            kwargs, 'workers', 'step_workers', 'handlers', 'task_handlers', default=None
        )
        if not isinstance(workers, dict):
            workers = {}
        steps = ('read', 'parse', 'chunk', 'embed', 'save', 'cascade', 'delta')
        default_workers = {step: None for step in steps}
        default_workers.update(workers or {})
        # also standard ingestion step names
        for name in ('read_parse', 'chunking', 'embedding', 'saving', 'cascading'):
            default_workers.setdefault(name, None)
        self.workers = default_workers
        self.step_workers = self.workers
        self.handlers = self.workers

        # queues state
        self._queue_state: dict[str, list[dict[str, Any]]] = {}
        self._sent: list[dict[str, Any]] = []
        self._dead_letters: list[dict[str, Any]] = []
        self._retry_list: list[dict[str, Any]] = _JobRetryList()
        self.dead_letters = self._dead_letters
        self.dead_lettered = self._dead_letters
        self.retry_list = self._retry_list
        self.retry_queue = self._retry_list
        self.dlq = self._dead_letters
        self._receive_counts: dict[str, int] = {}
        self._inflight: dict[str, int] = {}
        self._receipts: dict[str, dict[str, Any]] = {}

        # keep extras
        for key, value in kwargs.items():
            if key not in self.__dict__:
                try:
                    setattr(self, key, value)
                except Exception:
                    pass

    # ------------------------------------------------------------------ helpers
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

    def _queue_url_for(self, queue: Any = None, **kwargs: Any) -> str:
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

    def _track_receive_count(self, msg: dict[str, Any]) -> int:
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
    async def send(self, *args: Any, **kwargs: Any) -> Any:
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

        return (
            response
            if response is not None
            else {'MessageId': message_id, 'message_id': message_id}
        )

    # Aliases for send
    async def enqueue(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def publish(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def put(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def put_message(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def send_message(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def send_msg(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def push(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def submit(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def send_job(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def dispatch(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    async def enqueue_step(self, *args: Any, **kwargs: Any) -> Any:
        return await self.send(*args, **kwargs)

    # ------------------------------------------------------------------ receive
    async def receive(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        kwargs = dict(kwargs)
        company_filter = _first(
            kwargs, 'company_id', 'company', 'tenant_id', 'tenant', default=None
        )
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
                    self._dead_lettered_keys: set[str] = set()
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
    async def dequeue(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.receive(*args, **kwargs)

    async def receive_message(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.receive(*args, **kwargs)

    async def receive_messages(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.receive(*args, **kwargs)

    async def poll(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.receive(*args, **kwargs)

    async def get(self, *args: Any, company_id: Any = None, **kwargs: Any) -> list[dict[str, Any]]:
        if company_id is not None:
            kwargs.setdefault('company_id', company_id)
        return await self.receive(*args, **kwargs)

    async def get_messages(
        self, *args: Any, company_id: Any = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        if company_id is not None:
            kwargs.setdefault('company_id', company_id)
        return await self.receive(*args, **kwargs)

    async def receive_batch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.receive(*args, **kwargs)

    # ------------------------------------------------------------------ ack
    async def ack(self, *args: Any, **kwargs: Any) -> Any:
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
        queue_url = self._queue_url_for(
            _first(kwargs, 'queue', 'queue_url', default=None), **kwargs
        )

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
    async def acknowledge(self, *args: Any, **kwargs: Any) -> Any:
        return await self.ack(*args, **kwargs)

    async def ack_message(self, *args: Any, **kwargs: Any) -> Any:
        return await self.ack(*args, **kwargs)

    async def delete_message(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
        if company_id is not None:
            kwargs.setdefault('company_id', company_id)
        return await self.ack(*args, **kwargs)

    async def delete(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
        if company_id is not None:
            kwargs.setdefault('company_id', company_id)
        return await self.ack(*args, **kwargs)

    async def remove(self, *args: Any, **kwargs: Any) -> Any:
        return await self.ack(*args, **kwargs)

    async def complete(self, *args: Any, **kwargs: Any) -> Any:
        return await self.ack(*args, **kwargs)

    # ------------------------------------------------------------------ nack
    async def nack(self, *args: Any, **kwargs: Any) -> Any:
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
        queue_url = self._queue_url_for(
            _first(kwargs, 'queue', 'queue_url', default=None), **kwargs
        )
        client = self._get_sqs_client()
        if client is not None and hasattr(client, 'change_message_visibility'):
            try:
                client.change_message_visibility(
                    QueueUrl=queue_url, ReceiptHandle=_coerce_str(receipt), VisibilityTimeout=0
                )
            except Exception:
                pass
        # track retry
        self._retry_list.append(
            {'receipt_handle': receipt, 'reason': 'nack', 'queue_url': queue_url}
        )
        return True

    async def nack_message(self, *args: Any, **kwargs: Any) -> Any:
        return await self.nack(*args, **kwargs)

    async def fail(self, *args: Any, **kwargs: Any) -> Any:
        return await self.nack(*args, **kwargs)

    async def requeue(self, *args: Any, **kwargs: Any) -> Any:
        return await self.nack(*args, **kwargs)

    # ------------------------------------------------------------------ dlq
    async def dead_letter(self, *args: Any, **kwargs: Any) -> Any:
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
        queue_url = self._queue_url_for(
            _first(kwargs, 'queue', 'queue_url', default=None), **kwargs
        )
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

    async def dead_letter_message(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    async def move_to_dead_letter(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    async def move_to_dlq(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    async def route_to_dead_letter(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    async def send_to_dlq(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    async def redrive(self, *args: Any, **kwargs: Any) -> Any:
        return await self.dead_letter(*args, **kwargs)

    # ------------------------------------------------------------------ capacity
    def has_capacity(self, company_id: Any = None, **kwargs: Any) -> bool:
        cid = self._company_id(company_id) if company_id is not None else ''
        if _first(kwargs, 'company_id', 'company', default=None) is not None:
            cid = self._company_id(kwargs.get('company_id') or kwargs.get('company'))
        if not cid:
            return True
        return self._inflight.get(cid, 0) < (self.concurrency_cap or 1)

    async def can_acquire(self, *args: Any, **kwargs: Any) -> bool:
        company_id = _first(kwargs, 'company_id', 'company', default=None)
        if company_id is None and args:
            company_id = args[0]
        return self.has_capacity(company_id)

    async def acquire(self, *args: Any, **kwargs: Any) -> bool:
        company_id = _first(kwargs, 'company_id', 'company', default=None)
        if company_id is None and args:
            company_id = args[0]
        cid = self._company_id(company_id)
        if not cid:
            return True
        if self._inflight.get(cid, 0) >= (self.concurrency_cap or 1):
            return False
        self._inflight[cid] = self._inflight.get(cid, 0) + 1
        return True

    async def release_capacity(self, *args: Any, **kwargs: Any) -> bool:
        company_id = _first(kwargs, 'company_id', 'company', default=None)
        if company_id is None and args:
            company_id = args[0]
        cid = self._company_id(company_id)
        if cid and self._inflight.get(cid, 0) > 0:
            self._inflight[cid] -= 1
        return True

    async def release_slot(self, *args: Any, **kwargs: Any) -> bool:
        return await self.release_capacity(*args, **kwargs)

    async def release_concurrency(self, *args: Any, **kwargs: Any) -> bool:
        return await self.release_capacity(*args, **kwargs)

    async def release_concurrent(self, *args: Any, **kwargs: Any) -> bool:
        return await self.release_capacity(*args, **kwargs)

    async def free_slot(self, *args: Any, **kwargs: Any) -> bool:
        return await self.release_capacity(*args, **kwargs)

    async def release(self, *args: Any, **kwargs: Any) -> Any:
        await self.release_capacity(*args, **kwargs)
        return await self.nack(*args, **kwargs)

    async def acquire_slot(self, *args: Any, **kwargs: Any) -> bool:
        return await self.acquire(*args, **kwargs)

    # ------------------------------------------------------------------ sfn
    async def start_execution(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
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
        name = _first(
            kwargs, 'name', 'execution_name', 'execution_id', 'job_id', 'id', default=None
        )
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
                    response = client.start_execution(
                        stateMachineArn=arn, name=name, input=input_text
                    )
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

    async def start_step_functions_execution(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    async def start_state_machine(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    async def start_workflow(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    async def start_sfn(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    async def trigger(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    async def start_run(self, *args: Any, **kwargs: Any) -> Any:
        return await self.start_execution(*args, **kwargs)

    # per-step worker helpers
    def register_worker(self, step: Any, handler: Any = None, **kwargs: Any) -> None:
        key = _coerce_str(step)
        if handler is None:
            handler = kwargs.get('handler') or kwargs.get('worker')
        self.workers[key] = handler
        self.step_workers[key] = handler
        self.handlers[key] = handler

    def get_worker(self, step: Any, company_id: Any = None) -> Any:
        return self.workers.get(_coerce_str(step))

    async def invoke_worker(self, *args: Any, **kwargs: Any) -> Any:
        step = _first(kwargs, 'step', 'name', 'worker', default=None)
        if step is None and args:
            step = args[0]
            args = args[1:]
        handler = self.workers.get(_coerce_str(step)) if step is not None else None
        if handler is None:
            # default no-op
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

    # ------------------------------------------------------------------ sync helpers (best-effort)
    def send_sync(self, *args: Any, **kwargs: Any) -> Any:
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.send(*args, **kwargs))

    def receive_sync(self, *args: Any, **kwargs: Any) -> Any:
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.receive(*args, **kwargs))


# Aliases as class names
SqsAdapter = SqsQueue
QueueAdapter = SqsQueue
Queue = SqsQueue
OrchestrationAdapter = SqsQueue
OrchestrationQueue = SqsQueue
JobQueue = SqsQueue
StepFunctionsAdapter = SqsQueue
SQSQueue = SqsQueue
SqsClient = SqsQueue
Sqs = SqsQueue

__all__ = [
    'JobQueue',
    'OrchestrationAdapter',
    'OrchestrationQueue',
    'Queue',
    'QueueAdapter',
    'SQSQueue',
    'Sqs',
    'SqsAdapter',
    'SqsClient',
    'SqsQueue',
    'StepFunctionsAdapter',
]
