"""Port for queue and orchestration (SQS + Step Functions) operations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class QueuePort(ABC):
    """Interface for queue and orchestration operations."""

    @abstractmethod
    async def send(self, *args: object, **kwargs: object) -> object:
        """Send/enqueue a message."""
        raise NotImplementedError

    @abstractmethod
    async def receive(self, *args: object, **kwargs: object) -> object:
        """Receive/dequeue messages."""
        raise NotImplementedError

    async def ack(self, *args: object, **kwargs: object) -> object:
        """Acknowledge (delete) a received message."""
        return None

    async def nack(self, *args: object, **kwargs: object) -> object:
        """Negative-acknowledge a message (release / requeue)."""
        return None

    async def dead_letter(self, *args: object, **kwargs: object) -> object:
        """Route a message to the dead-letter queue."""
        return None

    async def start_execution(self, *args: object, **kwargs: object) -> object:
        """Start a Step Functions execution."""
        return None


Queue = QueuePort
QueueAdapter = QueuePort
SqsQueue = QueuePort
StepFunctionsQueue = QueuePort

__all__ = ['Queue', 'QueueAdapter', 'QueuePort', 'SqsQueue', 'StepFunctionsQueue']
