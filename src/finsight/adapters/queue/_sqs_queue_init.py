# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._sqs_queue_helpers import *


def _init_sqs_queue(self: Any, *args: Any, **kwargs: Any) -> None:
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
                    getattr(self.config, attr, None) if not isinstance(self.config, dict) else None
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
    workers = _first(kwargs, 'workers', 'step_workers', 'handlers', 'task_handlers', default=None)
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
    self._queue_state = {}
    self._sent = []
    self._dead_letters = []
    self._retry_list = _JobRetryList()
    self.dead_letters = self._dead_letters
    self.dead_lettered = self._dead_letters
    self.retry_list = self._retry_list
    self.retry_queue = self._retry_list
    self.dlq = self._dead_letters
    self._receive_counts = {}
    self._inflight = {}
    self._receipts = {}

    # keep extras
    for key, value in kwargs.items():
        if key not in self.__dict__:
            try:
                setattr(self, key, value)
            except Exception:
                pass


# ------------------------------------------------------------------ helpers
