"""Integration test suite fixtures.

Runs the test-environment bootstrap once per session (companies, document
versions, S3 fixture uploads) before any integration test executes.  When the
infrastructure (PostgreSQL) is not reachable the bootstrap is skipped, mirroring
the skip behaviour of the individual integration tests.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from finsight.core.config import load_config

if TYPE_CHECKING:
    from collections.abc import Generator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / 'scripts'

# Expose the bootstrap modules for import.
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / 'bootstrap'))

from bootstrap.main import main as bootstrap_main


def _postgres_reachable() -> bool:
    """True when the test-profile PostgreSQL instance answers TCP."""
    try:
        settings = load_config('test').vector_store
        with socket.create_connection((str(settings.host), int(settings.port)), timeout=2):
            return True
    except Exception:  # pragma: no cover - exercised only without Postgres  # noqa: BLE001
        return False
    return False


@pytest.fixture(scope='session', autouse=True)
def bootstrap_test_environment() -> Generator[None, None, None]:
    """Bootstrap the test environment once per session.

    Creates the fixture companies and document versions in PostgreSQL and
    uploads the fixture files to LocalStack S3. Skipped when infrastructure
    is not available (plain unit-test runs never load this conftest).
    """
    if not _postgres_reachable():
        # Infrastructure is down: skip only the bootstrap, not the tests.
        # Tests that require PostgreSQL carry their own skip guards; the rest
        # (contract tests over fakes) still run.
        yield
        return

    if os.environ.get('ENVIRONMENT') != 'test':
        os.environ['ENVIRONMENT'] = 'test'

    # Ensure dummy AWS credentials for config seam.
    os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
    os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')
    os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
    os.environ.setdefault('AWS_REGION', 'us-east-1')

    logging.getLogger('bootstrap_test_data').setLevel(logging.WARNING)
    result = asyncio.run(bootstrap_main())
    if result != 0:
        pytest.fail(f'Test environment bootstrap failed with exit code {result}')

    yield
