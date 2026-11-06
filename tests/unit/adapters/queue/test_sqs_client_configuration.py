"""SQS adapter client configuration tests (issue #237)."""

from __future__ import annotations

from unittest.mock import call, patch

import pytest

from finsight.adapters.queue.sqs_queue import SqsQueue

_BOTO3_CLIENT = 'finsight.adapters.queue._sqs_queue_misc.boto3.client'


@pytest.fixture(autouse=True)
def _clear_aws_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        'AWS_ENDPOINT_URL',
        'AWS_REGION',
        'AWS_DEFAULT_REGION',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
    ):
        monkeypatch.delenv(name, raising=False)


def test_localstack_queue_url_configures_sqs_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'local-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'local-secret')
    queue = SqsQueue(ingestion_queue_url='http://localhost:4566/000000000000/ingest')

    with patch(_BOTO3_CLIENT) as client_factory:
        client_factory.return_value = object()

        assert queue._get_sqs_client() is client_factory.return_value

    client_factory.assert_called_once_with(
        'sqs',
        endpoint_url='http://localhost:4566',
        region_name='us-west-2',
        aws_access_key_id='local-key',
        aws_secret_access_key='local-secret',
    )


def test_real_aws_queue_url_uses_queue_host_as_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    queue = SqsQueue(ingestion_queue_url='https://sqs.us-east-1.amazonaws.com/123456789012/ingest')

    with patch(_BOTO3_CLIENT) as client_factory:
        client_factory.return_value = object()

        assert queue._get_sqs_client() is client_factory.return_value

    kwargs = client_factory.call_args.kwargs
    assert kwargs['endpoint_url'] == 'https://sqs.us-east-1.amazonaws.com'
    assert kwargs['region_name'] == 'us-east-1'


def test_endpoint_falls_back_to_environment_when_queue_url_is_a_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('AWS_ENDPOINT_URL', 'http://localstack:4566')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'env-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'env-secret')
    queue = SqsQueue()

    with patch(_BOTO3_CLIENT) as client_factory:
        client_factory.return_value = object()

        queue._get_sqs_client()

    kwargs = client_factory.call_args.kwargs
    assert kwargs['endpoint_url'] == 'http://localstack:4566'
    assert kwargs['aws_access_key_id'] == 'env-key'
    assert kwargs['aws_secret_access_key'] == 'env-secret'


def test_step_functions_client_uses_the_same_localstack_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'local-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'local-secret')
    queue = SqsQueue(ingestion_queue_url='http://localhost:4566/000000000000/ingest')

    with patch(_BOTO3_CLIENT) as client_factory:
        client_factory.return_value = object()

        queue._get_sqs_client()
        assert queue._get_sfn_client() is client_factory.return_value

    assert client_factory.call_args_list[-1] == call(
        'stepfunctions',
        endpoint_url='http://localhost:4566',
        region_name='us-west-2',
        aws_access_key_id='local-key',
        aws_secret_access_key='local-secret',
    )


def test_sqs_client_creation_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    queue = SqsQueue(ingestion_queue_url='http://localhost:4566/000000000000/ingest')

    with patch(_BOTO3_CLIENT, side_effect=RuntimeError('no credentials')):
        assert queue._get_sqs_client() is None
