"""Regression tests for empty SQS receives (issue #238)."""

from __future__ import annotations

import pytest

from finsight.adapters.queue.sqs_queue import SqsQueue

pytestmark = pytest.mark.contract


class _EmptyMessagesClient:
    def receive_message(self, **kwargs: object) -> dict:
        return {'Messages': []}


class _MetadataOnlyClient:
    def receive_message(self, **kwargs: object) -> dict:
        return {'ResponseMetadata': {'RequestId': 'x', 'HTTPStatusCode': 200}}


class _SingleMessageDictClient:
    def receive_message(self, **kwargs: object) -> dict:
        return {
            'Body': '{"hello": "world"}',
            'ReceiptHandle': 'receipt-1',
            'MessageId': 'msg-1',
            'Attributes': {'ApproximateReceiveCount': '1'},
        }


async def test_empty_messages_list_returns_empty_list() -> None:
    queue = SqsQueue(sqs_client=_EmptyMessagesClient(), state_machine_arn=None)
    assert await queue.receive() == []


async def test_metadata_only_response_returns_empty_list() -> None:
    queue = SqsQueue(sqs_client=_MetadataOnlyClient(), state_machine_arn=None)
    assert await queue.receive() == []


async def test_single_message_dict_returns_one_element() -> None:
    queue = SqsQueue(sqs_client=_SingleMessageDictClient(), state_machine_arn=None)
    messages = await queue.receive()
    assert isinstance(messages, list)
    assert len(messages) == 1


async def test_null_internal_accumulator_is_safe() -> None:
    queue = SqsQueue(sqs_client=_EmptyMessagesClient(), state_machine_arn=None)
    queue._queue_state = None
    messages = await queue.receive()
    assert isinstance(messages, list)
    assert messages == []
