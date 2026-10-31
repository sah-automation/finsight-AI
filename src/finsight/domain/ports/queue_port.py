"""Port for queue and orchestration (SQS + Step Functions) operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class QueuePort(ABC):
    """Interface for queue and orchestration operations."""

    @abstractmethod
    async def send(self, *args: Any, **kwargs: Any) -> Any:
        """Send/enqueue a message."""
        raise NotImplementedError

    @abstractmethod
    async def receive(self, *args: Any, **kwargs: Any) -> Any:
        """Receive/dequeue messages."""
        raise NotImplementedError

    async def ack(self, *args: Any, **kwargs: Any) -> Any:
        """Acknowledge (delete) a received message."""
        return None

    async def nack(self, *args: Any, **kwargs: Any) -> Any:
        """Negative-acknowledge a message (release / requeue)."""
        return None

    async def dead_letter(self, *args: Any, **kwargs: Any) -> Any:
        """Route a message to the dead-letter queue."""
        return None

    async def start_execution(self, *args: Any, **kwargs: Any) -> Any:
        """Start a Step Functions execution."""
        return None


Queue = QueuePort
QueueAdapter = QueuePort
SqsQueue = QueuePort
StepFunctionsQueue = QueuePort

__all__ = ['Queue', 'QueueAdapter', 'QueuePort', 'SqsQueue', 'StepFunctionsQueue']
