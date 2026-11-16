"""Tests for the live smoke test script.

The smoke test script (Stage D-5) is the final gate of the deploy workflow.
It hits the live custom domain and verifies:
1. GET /health returns 200 with {"status": "ok"}
2. POST /questions/ask returns a structured SSE answer envelope
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'smoke_test.py'


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location('smoke_test', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke_test_module = _load_script()


class TestSmokeTestScript:
    """Tests for the smoke test script."""

    def test_parse_sse_event_valid(self) -> None:
        """Test parsing a valid SSE event block."""
        block = 'event: status\ndata: {"status": "received", "question": "test"}'
        result = smoke_test_module._parse_sse_event(block)
        assert result is not None
        assert result['event'] == 'status'
        assert result['data'] == {'status': 'received', 'question': 'test'}

    def test_parse_sse_event_multiple_data_lines(self) -> None:
        """Test parsing SSE event with multiple data lines (concatenated with newline)."""
        block = 'event: delta\ndata: {"text": "Hello"}\ndata: {"text": " World"}'
        result = smoke_test_module._parse_sse_event(block)
        assert result is not None
        assert result['event'] == 'delta'
        # JSON parsing will fail on concatenated lines with newline, so it falls back to raw
        assert 'raw' in result['data']

    def test_parse_sse_event_empty_data(self) -> None:
        """Test parsing SSE event with empty data returns None."""
        block = 'event: status\ndata: '
        result = smoke_test_module._parse_sse_event(block)
        assert result is None

    def test_parse_sse_event_invalid_json_fallback(self) -> None:
        """Test parsing SSE event with invalid JSON falls back to raw."""
        block = 'event: delta\ndata: not valid json'
        result = smoke_test_module._parse_sse_event(block)
        assert result is not None
        assert result['event'] == 'delta'
        assert result['data']['raw'] == 'not valid json'

    def test_smoke_test_error_creation(self) -> None:
        """Test SmokeTestError creation with details."""
        exc = smoke_test_module.SmokeTestError('Test error', {'key': 'value'})
        assert str(exc) == 'Test error'
        assert exc.details == {'key': 'value'}

    def test_smoke_test_error_creation_no_details(self) -> None:
        """Test SmokeTestError creation without details."""
        exc = smoke_test_module.SmokeTestError('Test error')
        assert str(exc) == 'Test error'
        assert exc.details == {}

    def test_smoke_test_config_dataclass(self) -> None:
        """Test SmokeTestConfig dataclass creation."""
        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com',
            jwt_token='test-token',
            timeout=45.0,
            retries=5,
            retry_delay=10.0,
        )
        assert config.base_url == 'https://api.example.com'
        assert config.jwt_token == 'test-token'
        assert config.timeout == 45.0
        assert config.retries == 5
        assert config.retry_delay == 10.0

    def test_smoke_test_config_defaults(self) -> None:
        """Test SmokeTestConfig defaults."""
        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        assert config.jwt_token is None
        assert config.timeout == 30.0
        assert config.retries == 3
        assert config.retry_delay == 5.0

    @patch('httpx.Client')
    def test_make_http_client_without_token(self, mock_client_class) -> None:
        """Test creating HTTP client without JWT token."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)

        assert client is mock_client
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args.kwargs
        assert 'Authorization' not in call_kwargs['headers']

    @patch('httpx.Client')
    def test_make_http_client_with_token(self, mock_client_class) -> None:
        """Test creating HTTP client with JWT token."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com',
            jwt_token='test-token',
        )
        client = smoke_test_module._make_http_client(config)

        assert client is mock_client
        call_kwargs = mock_client_class.call_args.kwargs
        assert call_kwargs['headers']['Authorization'] == 'Bearer test-token'

    @patch('httpx.Client')
    def test_test_health_success(self, mock_client_class) -> None:
        """Test health check success."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_client.get.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        result = smoke_test_module.test_health('https://api.example.com', client)

        assert result == {'status': 'ok'}
        mock_client.get.assert_called_once_with('https://api.example.com/health')

    @patch('httpx.Client')
    def test_test_health_failure_status_code(self, mock_client_class) -> None:
        """Test health check failure with non-200 status."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_client.get.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_health('https://api.example.com', client)

        assert 'expected 200, got 500' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_health_failure_invalid_json(self, mock_client_class) -> None:
        """Test health check failure with invalid JSON."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError('Invalid JSON', '', 0)
        mock_response.text = 'not json'
        mock_client.get.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_health('https://api.example.com', client)

        assert 'invalid JSON' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_health_failure_unexpected_payload(self, mock_client_class) -> None:
        """Test health check failure with unexpected payload."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'error'}
        mock_client.get.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_health('https://api.example.com', client)

        assert 'unexpected payload' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_questions_ask_success(self, mock_client_class) -> None:
        """Test questions ask success with valid SSE stream."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        # Simulate SSE stream chunks - each chunk is a complete event block
        mock_response.iter_text.return_value = [
            'event: status\ndata: {"status": "received", "question": "health check"}\n\n',
            'event: status\ndata: {"status": "answering"}\n\n',
            'event: complete\ndata: {"done": true}\n\n',
        ]
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        result = smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'events' in result
        assert len(result['events']) == 3
        assert 'status' in result['event_types']
        assert 'complete' in result['event_types']

    @patch('httpx.Client')
    def test_test_questions_ask_failure_status_code(self, mock_client_class) -> None:
        """Test questions ask failure with non-200 status."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.read.return_value = b'Unauthorized'
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'expected 200, got 401' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_questions_ask_failure_wrong_content_type(self, mock_client_class) -> None:
        """Test questions ask failure with wrong content type."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.read.return_value = b'{}'
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'unexpected content-type' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_questions_ask_failure_empty_stream(self, mock_client_class) -> None:
        """Test questions ask failure with empty SSE stream."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        mock_response.iter_text.return_value = []
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'empty SSE stream' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_questions_ask_failure_no_status_event(self, mock_client_class) -> None:
        """Test questions ask failure when status event is missing."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        mock_response.iter_text.return_value = [
            'event: delta\ndata: {"text": "Hello"}\n\n',
            'event: complete\ndata: {"done": true}\n\n',
        ]
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'missing status event' in str(exc_info.value)

    @patch('httpx.Client')
    def test_test_questions_ask_failure_no_complete(self, mock_client_class) -> None:
        """Test questions ask failure when stream doesn't complete properly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        mock_response.iter_text.return_value = [
            'event: status\ndata: {"status": "received"}\n\n',
            'event: delta\ndata: {"text": "Hello"}\n\n',
        ]
        mock_client.stream.return_value.__enter__.return_value = mock_response

        config = smoke_test_module.SmokeTestConfig(base_url='https://api.example.com')
        client = smoke_test_module._make_http_client(config)
        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module.test_questions_ask('https://api.example.com', client)

        assert 'did not complete properly' in str(exc_info.value)

    def test_retry_with_logging_success(self) -> None:
        """Test _retry_with_logging succeeds on first attempt."""
        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com', retries=3, retry_delay=0.01
        )
        call_count = 0

        def attempt_fn(attempt: int) -> str:
            nonlocal call_count
            call_count += 1
            return 'success'

        result = smoke_test_module._retry_with_logging(attempt_fn, 'test', config)
        assert result == 'success'
        assert call_count == 1

    def test_retry_with_logging_retry_then_success(self) -> None:
        """Test _retry_with_logging retries then succeeds."""
        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com', retries=3, retry_delay=0.01
        )
        call_count = 0

        def attempt_fn(attempt: int) -> str:
            nonlocal call_count
            call_count += 1
            if attempt < 2:
                raise smoke_test_module.SmokeTestError('temporary failure')
            return 'success'

        result = smoke_test_module._retry_with_logging(attempt_fn, 'test', config)
        assert result == 'success'
        assert call_count == 2

    def test_retry_with_logging_all_fail_raises(self) -> None:
        """Test _retry_with_logging raises after all retries exhausted."""
        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com', retries=3, retry_delay=0.01
        )

        def attempt_fn(attempt: int) -> str:
            raise smoke_test_module.SmokeTestError('permanent failure')

        with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
            smoke_test_module._retry_with_logging(attempt_fn, 'test', config)

        assert 'permanent failure' in str(exc_info.value)

    def test_retry_with_logging_informational_returns_none(self) -> None:
        """Test _retry_with_logging returns None on failure when informational=True."""
        config = smoke_test_module.SmokeTestConfig(
            base_url='https://api.example.com', retries=3, retry_delay=0.01
        )

        def attempt_fn(attempt: int) -> str:
            raise smoke_test_module.SmokeTestError('permanent failure')

        result = smoke_test_module._retry_with_logging(
            attempt_fn, 'test', config, informational=True
        )
        assert result is None

    def test_build_config_from_env_and_args(self) -> None:
        """Test building config from environment and args."""
        with patch.dict(
            'os.environ',
            {
                'SMOKE_TEST_BASE_URL': 'https://env.example.com',
                'SMOKE_TEST_JWT_TOKEN': 'env-token',
                'SMOKE_TEST_TIMEOUT': '45',
                'SMOKE_TEST_RETRIES': '5',
                'SMOKE_TEST_RETRY_DELAY': '10',
            },
        ):
            args = argparse.Namespace(
                base_url=None,
                jwt_token=None,
                timeout=None,
                retries=None,
                retry_delay=None,
            )
            config = smoke_test_module._build_config_from_env_and_args(args)
            assert config.base_url == 'https://env.example.com'
            assert config.jwt_token == 'env-token'
            assert config.timeout == 45.0
            assert config.retries == 5
            assert config.retry_delay == 10.0

    def test_build_config_args_override_env(self) -> None:
        """Test CLI args override environment variables."""
        with patch.dict(
            'os.environ',
            {
                'SMOKE_TEST_BASE_URL': 'https://env.example.com',
                'SMOKE_TEST_TIMEOUT': '45',
            },
        ):
            args = argparse.Namespace(
                base_url='https://arg.example.com',
                jwt_token='arg-token',
                timeout=60.0,
                retries=10,
                retry_delay=20.0,
            )
            config = smoke_test_module._build_config_from_env_and_args(args)
            assert config.base_url == 'https://arg.example.com'
            assert config.jwt_token == 'arg-token'
            assert config.timeout == 60.0
            assert config.retries == 10
            assert config.retry_delay == 20.0

    def test_build_config_missing_base_url_raises(self) -> None:
        """Test missing base URL raises SmokeTestError."""
        with patch.dict('os.environ', {}, clear=True):
            args = argparse.Namespace(
                base_url=None,
                jwt_token=None,
                timeout=None,
                retries=None,
                retry_delay=None,
            )
            with pytest.raises(smoke_test_module.SmokeTestError) as exc_info:
                smoke_test_module._build_config_from_env_and_args(args)
            assert 'SMOKE_TEST_BASE_URL not set' in str(exc_info.value)
