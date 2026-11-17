#!/usr/bin/env python3
"""Live smoke tests against the deployed custom domain.

This script is the final gate of the deploy workflow. It hits the live
custom domain (never the raw API Gateway URL) and verifies:

1. GET /health returns 200 with the expected JSON: {"status": "ok"}
2. POST /ask returns a structured answer envelope (SSE stream)

No mutating operations are performed. A smoke failure fails the workflow
loudly; no rollback is triggered automatically (documented manual/alias
rollback covers it).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
import traceback
from collections.abc import Callable
from typing import Any

import httpx

HTTP_OK = 200


class SmokeTestError(Exception):
    """Raised when a smoke test assertion fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


@dataclasses.dataclass(frozen=True)
class SmokeTestConfig:
    """Configuration for smoke tests, injected rather than read from env."""

    base_url: str
    jwt_token: str | None = None
    timeout: float = 30.0
    retries: int = 3
    retry_delay: float = 5.0


def _make_http_client(config: SmokeTestConfig) -> httpx.Client:
    """Create an HTTP client from the smoke test configuration."""
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'finsight-smoke-test/1.0',
    }
    if config.jwt_token:
        headers['Authorization'] = f'Bearer {config.jwt_token}'
    return httpx.Client(
        timeout=httpx.Timeout(config.timeout),
        follow_redirects=True,
        headers=headers,
    )


def _retry_with_logging(
    attempt_fn: Callable[[int], Any],
    label: str,
    config: SmokeTestConfig,
    *,
    informational: bool = False,
) -> Any:
    """Execute a function with retries and logging.

    Args:
        attempt_fn: Function that takes (attempt: int) and returns result or raises SmokeTestError
        label: Human-readable label for logging (e.g., "GET /health")
        config: Smoke test configuration with retries/retry_delay
        informational: If True, failures don't raise; just log warning and return None

    Returns:
        Result of attempt_fn on success, or None if informational and all retries exhausted.
    """
    for attempt in range(1, config.retries + 1):
        try:
            print(f'  Testing {label} (attempt {attempt}/{config.retries})...')
            return attempt_fn(attempt)
        except SmokeTestError as exc:
            print(f'  ✗ {label} failed: {exc}')
            if attempt < config.retries:
                print(f'  Retrying in {config.retry_delay}s...')
                time.sleep(config.retry_delay)
            else:
                if informational:
                    print(f'  ⚠ {label} failed but continuing (informational only)')
                    return None
                raise
    return None


def test_health(base_url: str, client: httpx.Client) -> dict[str, Any]:
    """Test GET /health endpoint.

    Expected: 200 OK with JSON {"status": "ok"}
    """
    url = f'{base_url}/health'
    response = client.get(url)

    if response.status_code != HTTP_OK:
        raise SmokeTestError(
            f'Health check failed: expected {HTTP_OK}, got {response.status_code}',
            {'url': url, 'status_code': response.status_code, 'body': response.text},
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise SmokeTestError(
            f'Health check returned invalid JSON: {exc}',
            {'url': url, 'body': response.text},
        ) from exc

    if not isinstance(data, dict) or data.get('status') != 'ok':
        raise SmokeTestError(
            f'Health check returned unexpected payload: {data}',
            {'url': url, 'expected': {'status': 'ok'}, 'actual': data},
        )

    return data


def test_ask(base_url: str, client: httpx.Client) -> dict[str, Any]:
    """Test POST /ask endpoint.

    Expected: 200 OK with SSE stream containing a structured answer envelope.
    We verify the stream starts and contains at least a 'status' event.
    """
    url = f'{base_url}/ask'
    # Use a reserved test tenant that is guaranteed read-only
    payload = {
        'question': 'health check',
        'company_id': 'smoke-test-readonly-tenant',
    }

    # The ask endpoint returns a streaming SSE response
    # We need to read the stream and verify it produces valid events
    with client.stream('POST', url, json=payload) as response:
        if response.status_code != HTTP_OK:
            body = response.read().decode('utf-8', errors='replace')
            raise SmokeTestError(
                f'Questions ask failed: expected {HTTP_OK}, got {response.status_code}',
                {'url': url, 'status_code': response.status_code, 'body': body},
            )

        # Verify content type is SSE
        content_type = response.headers.get('content-type', '')
        if 'text/event-stream' not in content_type:
            body = response.read().decode('utf-8', errors='replace')
            raise SmokeTestError(
                f'Questions ask returned unexpected content-type: {content_type}',
                {'url': url, 'content_type': content_type, 'body': body[:500]},
            )

        # Read the SSE stream and verify it has valid events
        events = []
        buffer = ''
        for chunk in response.iter_text():
            buffer += chunk
            while '\n\n' in buffer:
                event_block, buffer = buffer.split('\n\n', 1)
                event_data = _parse_sse_event(event_block)
                if event_data:
                    events.append(event_data)

        if not events:
            raise SmokeTestError(
                'Questions ask returned empty SSE stream',
                {'url': url, 'events': events},
            )

        # Verify we got at least a status event (received/answering) and a complete event
        event_types = {e.get('event') for e in events}
        if 'status' not in event_types:
            raise SmokeTestError(
                'Questions ask SSE stream missing status event',
                {'url': url, 'events': events},
            )

        # Verify the stream ends with a complete event
        if not any(e.get('event') == 'complete' for e in events):
            # Check if the last event has done: true
            last_event = events[-1] if events else {}
            last_data = last_event.get('data', {})
            if not isinstance(last_data, dict) or not last_data.get('done'):
                raise SmokeTestError(
                    'Questions ask SSE stream did not complete properly',
                    {'url': url, 'events': events},
                )

        return {'events': events, 'event_types': list(event_types)}


def _parse_sse_event(block: str) -> dict[str, Any] | None:
    """Parse a single SSE event block.

    Per the SSE spec, multiple 'data:' lines are concatenated with a newline
    between them to form the complete data payload. Each data line is stripped
    of leading whitespace before joining.
    """
    event_type = 'message'
    data_lines: list[str] = []

    for line in block.split('\n'):
        if line.startswith('event:'):
            event_type = line[6:].strip()
        elif line.startswith('data:'):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None

    # Join with newline as per SSE spec
    data = '\n'.join(data_lines)

    if not data:
        return None

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError:
        parsed_data = {'raw': data}

    return {'event': event_type, 'data': parsed_data}


def run_smoke_tests(config: SmokeTestConfig) -> int:
    """Run all smoke tests against the deployed API.

    Returns 0 on success, non-zero on failure.
    """
    print(f'Running smoke tests against: {config.base_url}')
    print(
        f'Timeout: {config.timeout}s, Retries: {config.retries}, Retry delay: {config.retry_delay}s'
    )
    if config.jwt_token:
        print('Using JWT authentication for requests')
    else:
        print('No JWT token provided; health check may work if public, ask endpoint will fail')

    client = _make_http_client(config)

    # Test health endpoint with retries
    def health_attempt(attempt: int) -> dict[str, Any]:
        return test_health(config.base_url, client)

    _retry_with_logging(health_attempt, 'GET /health', config)
    print('  ✓ Health check passed')

    # Test questions/ask endpoint with retries
    def ask_attempt(attempt: int) -> dict[str, Any]:
        return test_ask(config.base_url, client)

    ask_result = _retry_with_logging(ask_attempt, 'POST /ask', config)
    print('  ✓ Questions ask passed')
    print(f'    Event types: {ask_result["event_types"]}')

    print('\n✓ All smoke tests passed')
    return 0


def _build_config_from_env_and_args(args: argparse.Namespace) -> SmokeTestConfig:
    """Build configuration from environment variables and CLI args.

    CLI args take precedence over environment variables.
    """
    base_url = args.base_url or os.environ.get('SMOKE_TEST_BASE_URL')
    if not base_url:
        raise SmokeTestError('SMOKE_TEST_BASE_URL not set (via --base-url or env)')

    jwt_token = args.jwt_token or os.environ.get('SMOKE_TEST_JWT_TOKEN')

    timeout = args.timeout
    if timeout is None:
        timeout = float(os.environ.get('SMOKE_TEST_TIMEOUT', '30'))

    retries = args.retries
    if retries is None:
        retries = int(os.environ.get('SMOKE_TEST_RETRIES', '3'))

    retry_delay = args.retry_delay
    if retry_delay is None:
        retry_delay = float(os.environ.get('SMOKE_TEST_RETRY_DELAY', '5'))

    return SmokeTestConfig(
        base_url=base_url.rstrip('/'),
        jwt_token=jwt_token,
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
    )


def main() -> int:
    """Parse arguments and run smoke tests."""
    parser = argparse.ArgumentParser(description='Run live smoke tests against deployed API')
    parser.add_argument(
        '--base-url',
        help='Base URL of the deployed API (overrides SMOKE_TEST_BASE_URL)',
    )
    parser.add_argument(
        '--jwt-token',
        help='JWT token for authenticated requests (overrides SMOKE_TEST_JWT_TOKEN)',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        help='Request timeout in seconds (overrides SMOKE_TEST_TIMEOUT)',
    )
    parser.add_argument(
        '--retries',
        type=int,
        help='Number of retries (overrides SMOKE_TEST_RETRIES)',
    )
    parser.add_argument(
        '--retry-delay',
        type=float,
        help='Delay between retries in seconds (overrides SMOKE_TEST_RETRY_DELAY)',
    )
    args = parser.parse_args()

    try:
        config = _build_config_from_env_and_args(args)
        return run_smoke_tests(config)
    except SmokeTestError as exc:
        print(f'\n✗ Smoke test failed: {exc}', file=sys.stderr)
        if exc.details:
            print(f'Details: {json.dumps(exc.details, indent=2)}', file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f'\n✗ Unexpected error: {exc}', file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
