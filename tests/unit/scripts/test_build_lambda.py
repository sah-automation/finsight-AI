"""Tests for the Lambda packaging script.

The deploy pipeline (Stage D-2) uploads ``api.zip`` as a workflow artifact and
CDK deploys it verbatim, so the archive must be a complete, self-contained
deployment package: the application rooted at ``finsight/`` (the CDK handler
``finsight.entrypoints.api.main.handler`` imports from the Lambda task root),
``config/`` beside it, and the vendored runtime dependencies at the archive
root. The build is deterministic — a rebuild from the same inputs must produce
a byte-identical archive and matching checksum.

These tests run hermetically against a fake source tree and a fake
dependencies directory; the real dependency vendoring commands are asserted as
command vectors, never executed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'build_lambda.py'


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location('build_lambda', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_lambda_module = _load_script()


@pytest.fixture()
def source_tree(tmp_path: Path) -> Path:
    """A minimal fake repository tree with the bundle paths plus junk files."""
    (tmp_path / 'src' / 'finsight' / 'core').mkdir(parents=True)
    (tmp_path / 'src' / 'finsight' / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / 'src' / 'finsight' / 'core' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config' / 'schema.yaml').write_text('app: {}\n', encoding='utf-8')
    # Junk that must never reach the archive.
    (tmp_path / 'src' / 'finsight' / '.DS_Store').write_bytes(b'\x00\x01')
    pycache = tmp_path / 'src' / 'finsight' / 'core' / '__pycache__'
    pycache.mkdir()
    (pycache / 'app.cpython-312.pyc').write_bytes(b'\x00\x01')
    return tmp_path


@pytest.fixture()
def deps_dir(tmp_path: Path) -> Path:
    """A fake vendored-dependencies tree (site-packages layout at its root)."""
    deps = tmp_path / 'deps'
    (deps / 'fastapi').mkdir(parents=True)
    (deps / 'fastapi' / '__init__.py').write_text('', encoding='utf-8')
    (deps / 'boto3').mkdir(parents=True)
    (deps / 'boto3' / '__init__.py').write_text('', encoding='utf-8')
    return deps


def _zip_names(archive_path: Path) -> set[str]:
    with zipfile.ZipFile(archive_path) as archive:
        return set(archive.namelist())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_application_package_is_rooted_at_finsight(source_tree: Path, tmp_path: Path) -> None:
    """The archive root holds finsight/ directly so the CDK handler imports."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(output, source_root=source_tree)

    names = _zip_names(output / 'api.zip')
    assert 'finsight/__init__.py' in names
    assert 'finsight/core/app.py' in names
    assert not any(name.startswith('src/') for name in names), names


def test_config_travels_beside_the_package(source_tree: Path, tmp_path: Path) -> None:
    """config/ is a sibling of finsight/ so the loader resolves it at runtime."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(output, source_root=source_tree)

    assert 'config/schema.yaml' in _zip_names(output / 'api.zip')


def test_vendored_dependencies_land_at_archive_root(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """Runtime dependencies are flattened into the archive root."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(output, source_root=source_tree, deps_dir=deps_dir)

    names = _zip_names(output / 'api.zip')
    assert 'fastapi/__init__.py' in names
    assert 'boto3/__init__.py' in names


def test_junk_files_are_excluded(source_tree: Path, tmp_path: Path) -> None:
    """OS and bytecode junk never reaches the archive."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(output, source_root=source_tree)

    names = _zip_names(output / 'api.zip')
    assert not any('.DS_Store' in name for name in names), names
    assert not any('__pycache__' in name for name in names), names
    assert not any(name.endswith(('.pyc', '.pyo')) for name in names), names


def test_build_is_deterministic_with_matching_checksum(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """Two builds from the same inputs are byte-identical, with a valid checksum."""
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    build_lambda_module.build_lambda(first, source_root=source_tree, deps_dir=deps_dir)
    build_lambda_module.build_lambda(second, source_root=source_tree, deps_dir=deps_dir)

    first_zip, second_zip = first / 'api.zip', second / 'api.zip'
    assert _sha256(first_zip) == _sha256(second_zip)

    checksum_file = first / 'api.zip.sha256'
    assert checksum_file.read_text(encoding='utf-8') == (f'{_sha256(first_zip)}  api.zip\n')


def test_default_build_vendors_runtime_deps_from_the_lockfile(
    source_tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an explicit deps dir the script vendors deps, then cleans up."""
    output = tmp_path / 'out'
    vendored_into: list[Path] = []

    def fake_vendor(deps_dir: Path) -> None:
        deps_dir.mkdir(parents=True, exist_ok=True)
        (deps_dir / 'fastapi').mkdir()
        (deps_dir / 'fastapi' / '__init__.py').write_text('', encoding='utf-8')
        vendored_into.append(deps_dir)

    monkeypatch.setattr(build_lambda_module, '_vendor_runtime_deps', fake_vendor)
    build_lambda_module.build_lambda(output, source_root=source_tree)

    assert vendored_into == [output / 'deps']
    assert 'fastapi/__init__.py' in _zip_names(output / 'api.zip')
    # The staging directory is removed after packaging; dist keeps zip + checksum.
    assert not (output / 'deps').exists()
    assert sorted(path.name for path in output.iterdir()) == ['api.zip', 'api.zip.sha256']


def test_dependency_vendoring_commands_pin_the_lambda_platform(tmp_path: Path) -> None:
    """Deps are installed frozen, targeted, and for the Lambda runtime platform."""
    requirements = tmp_path / 'runtime-requirements.txt'
    deps = tmp_path / 'deps'

    commands = build_lambda_module._runtime_deps_commands(requirements, deps)

    export, install = commands
    joined_export = ' '.join(export)
    assert 'export' in joined_export
    assert '--frozen' in export
    assert '--no-dev' in export
    assert '--no-emit-project' in export
    assert str(requirements) in export

    joined_install = ' '.join(install)
    assert 'pip' in joined_install and 'install' in joined_install
    assert '--no-deps' in install
    assert '--no-compile' in install
    assert '--python-platform' in install
    assert 'x86_64-unknown-linux-gnu' in install
    assert '--python-version' in install
    assert '3.12' in install
    assert str(deps) in install
