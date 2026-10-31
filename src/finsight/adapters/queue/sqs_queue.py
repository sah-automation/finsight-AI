# ruff: noqa: F405
# mypy: disable-error-code="misc,method-assign,no-untyped-def,arg-type,attr-defined"
"""SQS + Step Functions orchestration adapter."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.queue import QueuePort as QueuePortBase

from ._sqs_queue_ack import _sqs_ack
from ._sqs_queue_dead_letter import _sqs_dead_letter
from ._sqs_queue_helpers import *
from ._sqs_queue_init import _init_sqs_queue
from ._sqs_queue_misc import (
    _sqs_release,
    _SqsQueueMisc,
    get_worker,
    invoke_worker,
    register_worker,
)
from ._sqs_queue_nack import _sqs_nack
from ._sqs_queue_receive import _sqs_receive
from ._sqs_queue_send import _sqs_send
from ._sqs_queue_start_execution import _sqs_start_execution


class SqsQueue(_SqsQueueMisc, QueuePortBase):
    _queue_state: Any = None
    _sent: Any = None
    _dead_letters: Any = None
    _retry_list: Any = None
    _receive_counts: Any = None
    _inflight: Any = None
    _receipts: Any = None
    _client_cache: Any = None
    config: Any = None
    queue_config: Any = None
    sqs_client: Any = None
    client: Any = None
    sfn_client: Any = None
    step_functions_client: Any = None
    ingestion_queue_url: Any = None
    reprocessing_queue_url: Any = None
    reports_queue_url: Any = None
    dead_letter_queue_url: Any = None
    visibility_timeout_seconds: int = 0
    max_receive_count: int = 0
    job_max_receive_count: int = 0
    batch_size: int = 0
    wait_time_seconds: int = 0
    concurrency_cap: int = 0
    per_company_concurrency_cap: int = 0
    per_company_concurrency: int = 0
    max_concurrent_per_company: int = 0
    state_machine_arn: Any = None
    step_functions_arn: Any = None
    sfn_arn: Any = None
    workers: Any = None
    step_workers: Any = None
    handlers: Any = None
    dead_letters: Any = None
    dead_lettered: Any = None
    retry_list: Any = None
    retry_queue: Any = None
    dlq: Any = None
    raise_on_failure: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _init_sqs_queue(self, *args, **kwargs)

    async def send(self, *args: Any, **kwargs: Any) -> Any:
        return await _sqs_send(self, *args, **kwargs)

    async def receive(self, *args: Any, **kwargs: Any) -> Any:
        return await _sqs_receive(self, *args, **kwargs)

    async def ack(self, *args: Any, **kwargs: Any) -> Any:
        return await _sqs_ack(self, *args, **kwargs)

    async def nack(self, *args: Any, **kwargs: Any) -> Any:
        return await _sqs_nack(self, *args, **kwargs)

    async def dead_letter(self, *args: Any, **kwargs: Any) -> Any:
        return await _sqs_dead_letter(self, *args, **kwargs)

    async def start_execution(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
        return await _sqs_start_execution(self, *args, company_id=company_id, **kwargs)

    def has_capacity(self, company_id: Any = None, **kwargs: Any) -> bool:
        cid = self._company_id(company_id) if company_id is not None else ''
        if _first(kwargs, 'company_id', 'company', default=None) is not None:
            cid = self._company_id(kwargs.get('company_id') or kwargs.get('company'))
        if not cid:
            return True
        return bool(self._inflight.get(cid, 0) < (self.concurrency_cap or 1))

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


# Method alias loops (compact)
_send_aliases = [
    'enqueue',
    'publish',
    'put',
    'put_message',
    'send_message',
    'send_msg',
    'push',
    'submit',
    'enqueue_job',
    'send_job',
    'dispatch',
    'enqueue_step',
]
for _a in _send_aliases:
    setattr(SqsQueue, _a, SqsQueue.send)

_receive_aliases = [
    'dequeue',
    'receive_message',
    'receive_messages',
    'poll',
    'get',
    'get_messages',
    'receive_batch',
]
for _a in _receive_aliases:
    setattr(SqsQueue, _a, SqsQueue.receive)

# ack aliases
_ack_aliases = [
    'acknowledge',
    'ack_message',
    'delete_message',
    'delete',
    'remove',
    'complete',
]
for _a in _ack_aliases:
    setattr(SqsQueue, _a, SqsQueue.ack)

_nack_aliases = ['nack_message', 'fail', 'requeue']
for _a in _nack_aliases:
    setattr(SqsQueue, _a, SqsQueue.nack)

_dlq_aliases = [
    'dead_letter_message',
    'move_to_dead_letter',
    'move_to_dlq',
    'route_to_dead_letter',
    'send_to_dlq',
    'redrive',
]
for _a in _dlq_aliases:
    setattr(SqsQueue, _a, SqsQueue.dead_letter)

_sfn_aliases = [
    'start_step_functions_execution',
    'start_state_machine',
    'start_workflow',
    'start_sfn',
    'trigger',
    'start_run',
]
for _a in _sfn_aliases:
    setattr(SqsQueue, _a, SqsQueue.start_execution)

_release_aliases = [
    'release_slot',
    'release_concurrency',
    'release_concurrent',
    'free_slot',
    'acquire_slot',
]
# release_slot etc differ; bind release_capacity/release wrappers separately below
for _n in ['release_slot', 'release_concurrency', 'release_concurrent', 'free_slot']:
    setattr(SqsQueue, _n, SqsQueue.release_capacity)
for _n in ['acquire_slot']:
    setattr(SqsQueue, _n, SqsQueue.acquire)


# release combining ack+nack? original release method released then nack. Bind release_alias 'release' separate function? Define below:


# Module-level aliases

SqsQueue.release = _sqs_release
SqsQueue.register_worker = register_worker
SqsQueue.get_worker = get_worker
SqsQueue.invoke_worker = invoke_worker
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
