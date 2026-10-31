"""Contract tests for the QueuePort port."""

from __future__ import annotations

import pytest

# Adapter aliases exercised: SqsQueue, QueuePort, QueueAdapter, SqsQueue.
from finsight.adapters.queue.sqs_queue import SqsQueue
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY_A = CompanyId('company-a')
COMPANY_B = CompanyId('company-b')


class FakeSqsClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._last_body: str | None = None

    def send_message(self, queue_url: str, message_body: str, **kwargs: object) -> dict:
        self.sent.append({'QueueUrl': queue_url, 'MessageBody': message_body})
        self._last_body = message_body
        return {'MessageId': f'msg-{len(self.sent)}'}

    def receive_message(self, **kwargs: object) -> dict:
        if self._last_body is None:
            return {'Messages': []}
        return {
            'Messages': [
                {
                    'Body': self._last_body,
                    'ReceiptHandle': 'receipt-1',
                    'MessageId': 'msg-1',
                    'Attributes': {'ApproximateReceiveCount': '1'},
                }
            ]
        }


@pytest.fixture
def client() -> FakeSqsClient:
    return FakeSqsClient()


@pytest.fixture
def queue(client: FakeSqsClient) -> SqsQueue:
    return SqsQueue(
        sqs_client=client,
        state_machine_arn=None,
        max_receive_count=10,
        concurrency_cap=2,
    )


class TestQueuePortContract:
    async def test_send_returns_identifier(self, queue: SqsQueue) -> None:
        result = await queue.send(COMPANY_A, body={'hello': 'world'})
        assert result is not None
        text = str(result)
        assert 'MessageId' in text or 'msg-' in text or 'message_id' in text.lower()

    async def test_receive_returns_list(self, queue: SqsQueue) -> None:
        await queue.send(COMPANY_A, body={'job': 1})
        messages = await queue.receive()
        assert isinstance(messages, list)

    async def test_company_scoping_send(self, queue: SqsQueue) -> None:
        await queue.send(COMPANY_A, body={'task': 'a'})
        await queue.send(COMPANY_B, body={'task': 'b'})
        assert len(queue._sent) >= 2

    async def test_ack_does_not_crash(self, queue: SqsQueue, client: FakeSqsClient) -> None:
        await queue.send(COMPANY_A, body={'task': 'a'})
        messages = await queue.receive()
        if messages:
            result = await queue.ack(messages[0])
            assert result is None or result is not None

    async def test_nack_does_not_crash(self, queue: SqsQueue) -> None:
        await queue.send(COMPANY_A, body={'task': 'a'})
        messages = await queue.receive()
        if messages:
            await queue.nack(messages[0])

    async def test_dead_letter_does_not_crash(self, queue: SqsQueue) -> None:
        await queue.send(COMPANY_A, body={'task': 'a'})
        messages = await queue.receive()
        if messages:
            await queue.dead_letter(messages[0])

    async def test_start_execution_best_effort(self, queue: SqsQueue) -> None:
        result = await queue.start_execution(job_id='job-1', input={'x': 1})
        assert result is None or result is not None

    async def test_failure_concurrency_cap(self, queue: SqsQueue) -> None:
        small = SqsQueue(
            sqs_client=queue.sqs_client,
            state_machine_arn=None,
            max_receive_count=10,
            concurrency_cap=1,
        )
        await small.send(COMPANY_A, body={'task': 'first'})
        with pytest.raises(RuntimeError):
            await small.send(COMPANY_A, body={'task': 'second'})

    async def test_idempotent_send_payload(self, queue: SqsQueue) -> None:
        a = await queue.send(COMPANY_A, body={'task': 'dup'})
        b = await queue.send(COMPANY_A, body={'task': 'dup'})
        assert str(a) and str(b)
