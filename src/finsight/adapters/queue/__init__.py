"""Queue and orchestration adapters."""

from __future__ import annotations

from .sqs_queue import (
    JobQueue,
    OrchestrationAdapter,
    OrchestrationQueue,
    Queue,
    QueueAdapter,
    Sqs,
    SqsAdapter,
    SqsClient,
    SQSQueue,
    SqsQueue,
    StepFunctionsAdapter,
)

# Backwards-friendly aliases.
SqsQueueAdapter = SqsQueue
SQS = SqsQueue
SqsQueueWrapper = SqsQueue
StepFunctionsQueue = SqsQueue
StepFunctionQueue = SqsQueue
Orchestration = SqsQueue
QueuePort = SqsQueue
QueueClient = SqsQueue

__all__ = [
    'SQS',
    'JobQueue',
    'Orchestration',
    'OrchestrationAdapter',
    'OrchestrationQueue',
    'Queue',
    'QueueAdapter',
    'QueueClient',
    'QueuePort',
    'SQSQueue',
    'Sqs',
    'SqsAdapter',
    'SqsClient',
    'SqsQueue',
    'SqsQueueAdapter',
    'SqsQueueWrapper',
    'StepFunctionQueue',
    'StepFunctionsAdapter',
    'StepFunctionsQueue',
]
