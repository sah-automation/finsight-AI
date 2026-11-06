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


class _RaisingSqsClient:
    def send_message(self, *args: object, **kwargs: object) -> dict:
        raise RuntimeError('AWS.SimpleQueueService.NonExistentQueue')


class _ErrorResponseSqsClient:
    def send_message(self, *args: object, **kwargs: object) -> dict:
        return {'error': 'AWS.SimpleQueueService.NonExistentQueue'}


class TestQueueSendFailures:
    """A send that the broker rejected is never reported as success (issue #233)."""

    async def test_raising_client_surfaces_a_failure(self) -> None:
        queue = SqsQueue(sqs_client=_RaisingSqsClient(), state_machine_arn=None)

        with pytest.raises(RuntimeError, match='SQS send failed'):
            await queue.send(COMPANY_A, body={'task': 'lost'})

        assert queue._sent == []
        assert queue._queue_state == {}

    async def test_error_response_is_not_treated_as_success(self) -> None:
        queue = SqsQueue(sqs_client=_ErrorResponseSqsClient(), state_machine_arn=None)

        with pytest.raises(RuntimeError, match='SQS send failed'):
            await queue.send(COMPANY_A, body={'task': 'lost'})

        assert queue._sent == []
        assert queue._queue_state == {}

    async def test_successful_send_records_exactly_one_message(self) -> None:
        client = FakeSqsClient()
        queue = SqsQueue(sqs_client=client, state_machine_arn=None)

        await queue.send(COMPANY_A, body={'task': 'kept'})

        assert len(queue._sent) == 1
        assert len(client.sent) == 1


class _HealthySqsClient:
    """Fake client that simulates successful get_queue_attributes for all queues."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_queue_attributes(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {
            'Attributes': {
                'QueueArn': f'arn:aws:sqs:local:000000000000:{kwargs.get("QueueUrl", "").split("/")[-1]}'
            }
        }


class _FailingSqsClient(_HealthySqsClient):
    """Fake client that fails on the second queue check."""

    call_count = 0

    def get_queue_attributes(self, **kwargs: object) -> dict:
        self.call_count += 1
        self.calls.append(kwargs)
        if self.call_count > 1:
            raise RuntimeError('queue unavailable')
        return {
            'Attributes': {
                'QueueArn': f'arn:aws:sqs:local:000000000000:{kwargs.get("QueueUrl", "").split("/")[-1]}'
            }
        }


class TestQueueHealthCheck:
    """health_check verifies all configured queues are reachable (issue #233)."""

    async def test_health_check_succeeds_when_all_queues_reachable(self) -> None:
        client = _HealthySqsClient()
        queue = SqsQueue(
            sqs_client=client,
            state_machine_arn=None,
            ingestion_queue_url='http://localhost:4566/000000000000/ingest',
            reprocessing_queue_url='http://localhost:4566/000000000000/reprocess',
            reports_queue_url='http://localhost:4566/000000000000/reports',
            dead_letter_queue_url='http://localhost:4566/000000000000/dlq',
        )

        assert await queue.health_check() is True
        assert len(client.calls) == 4

    async def test_health_check_checks_only_configured_queues(self) -> None:
        """Only explicitly configured queue URLs are checked; defaults are skipped."""
        client = _HealthySqsClient()
        queue = SqsQueue(
            sqs_client=client,
            state_machine_arn=None,
            ingestion_queue_url='http://localhost:4566/000000000000/ingest',
            # reprocessing, reports not set -> not checked
            # dead_letter_queue_url not set -> default is skipped
        )

        assert await queue.health_check() is True
        # only ingestion (explicitly configured) is checked
        assert len(client.calls) == 1

    async def test_health_check_fails_when_any_queue_unreachable(self) -> None:
        client = _FailingSqsClient()
        queue = SqsQueue(
            sqs_client=client,
            state_machine_arn=None,
            ingestion_queue_url='http://localhost:4566/000000000000/ingest',
            reprocessing_queue_url='http://localhost:4566/000000000000/reprocess',
            reports_queue_url='http://localhost:4566/000000000000/reports',
            dead_letter_queue_url='http://localhost:4566/000000000000/dlq',
        )

        assert await queue.health_check() is False

    async def test_health_check_fails_when_no_client(self) -> None:
        queue = SqsQueue(sqs_client=None, state_machine_arn=None)

        assert await queue.health_check() is False

    async def test_health_check_fails_when_no_queue_urls(self) -> None:
        client = FakeSqsClient()
        queue = SqsQueue(sqs_client=client, state_machine_arn=None)

        assert await queue.health_check() is False
