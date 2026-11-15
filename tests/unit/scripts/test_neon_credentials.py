"""Tests for the Neon credential capture and storage scripts.

The connection string must never be echoed, logged or committed: the capture
script writes it to a file with owner-only permissions, and the storage script
hands it to SSM in memory, verifies the parameter by metadata only, and then
destroys the local copy. These tests use fake clients and a temporary directory
and never touch AWS.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / 'scripts'


def _load(name: str) -> Any:
    path = SCRIPTS_DIR / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


capture = _load('capture_neon_credential')
store = _load('store_neon_parameter')

# A fake connection string, never a real credential. The pragma keeps the
# secret scanner from reading the user:password shape as Basic Auth.
DSN = 'postgresql://user:placeholder@ep-example.us-east-2.aws.neon.tech/db?sslmode=require'  # pragma: allowlist secret


class FakeSsm:
    """Minimal stand-in for the AWS SSM client."""

    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    def put_parameter(self, **kwargs: Any) -> dict[str, Any]:
        self.written.append(kwargs)
        return {}

    def describe_parameters(self, **kwargs: Any) -> dict[str, Any]:
        name = kwargs['ParameterFilters'][0]['Values'][0]
        return {
            'Parameters': [
                {
                    'Name': name,
                    'Type': 'SecureString',
                    'Version': 1,
                    'LastModifiedDate': '2026-11-15T00:00:00Z',
                }
            ]
        }


def test_capture_writes_the_credential_with_owner_only_permissions(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'

    capture.write_credential_file(DSN, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert store.read_value(target) == DSN


def test_capture_refuses_a_value_that_is_not_a_connection_string(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'

    with pytest.raises(ValueError, match='postgresql'):
        capture.write_credential_file('not-a-connection-string', target)

    assert not target.exists()


def test_capture_round_trips_a_value_containing_a_quote(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    dsn = f'{DSN}&x=o%27clock'

    capture.write_credential_file(dsn, target)

    assert store.read_value(target) == dsn


def test_store_reads_the_value_the_capture_script_wrote(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    capture.write_credential_file(DSN, target)

    assert store.read_value(target) == DSN


def test_store_rejects_a_file_without_the_credential(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    target.write_text('OTHER=value\n', encoding='utf-8')

    with pytest.raises(SystemExit, match='NEON_DATABASE_URL'):
        store.read_value(target)


def test_store_puts_the_value_in_ssm_as_a_secure_string(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    capture.write_credential_file(DSN, target)
    ssm = FakeSsm()

    store.store_parameter(ssm, store.read_value(target), '/finsight/prod/neon/database_url')

    assert len(ssm.written) == 1
    written = ssm.written[0]
    assert written['Name'] == '/finsight/prod/neon/database_url'
    assert written['Type'] == 'SecureString'
    assert written['Value'] == DSN
    assert written['Overwrite'] is True


def test_store_removes_the_local_copy_after_the_write(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    capture.write_credential_file(DSN, target)
    ssm = FakeSsm()

    store.store_and_verify(ssm, target, '/finsight/prod/neon/database_url')

    assert not target.exists()


def test_store_never_prints_the_value(tmp_path: Path, capsys: Any) -> None:
    target = tmp_path / 'neon.env'
    capture.write_credential_file(DSN, target)
    ssm = FakeSsm()
    password = DSN.split('://', 1)[1].split(':', 1)[1].split('@', 1)[0]

    store.store_and_verify(ssm, target, '/finsight/prod/neon/database_url')

    captured = capsys.readouterr()
    assert DSN not in captured.out
    assert password not in captured.out


def test_store_fails_loudly_when_the_parameter_is_missing(tmp_path: Path) -> None:
    target = tmp_path / 'neon.env'
    capture.write_credential_file(DSN, target)

    class EmptySsm(FakeSsm):
        def describe_parameters(self, **kwargs: Any) -> dict[str, Any]:
            return {'Parameters': []}

    with pytest.raises(SystemExit, match='not found'):
        store.store_and_verify(EmptySsm(), target, '/finsight/prod/neon/database_url')


def test_store_default_parameter_path_is_the_documented_one() -> None:
    assert store.PARAMETER_NAME == '/finsight/prod/neon/database_url'


def test_store_default_file_is_outside_the_repository() -> None:
    repo_root = SCRIPTS_DIR.parent
    assert not str(store.ENV_FILE).startswith(str(repo_root))
    assert store.ENV_FILE.name == 'neon.env'


def test_capture_default_file_is_outside_the_repository() -> None:
    repo_root = SCRIPTS_DIR.parent
    assert not str(capture.ENV_FILE).startswith(str(repo_root))


def test_capture_creates_the_directory_it_needs(tmp_path: Path) -> None:
    target = tmp_path / 'nested' / 'dir' / 'neon.env'

    capture.write_credential_file(DSN, target)

    assert target.is_file()
    assert os.access(target, os.R_OK)
