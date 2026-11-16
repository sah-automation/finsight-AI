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
    packages = (
        # API + gateway shared
        'fastapi',
        'boto3',
        'tokenizers',
        # litellm chain (gateway only)
        'litellm',
        'openai',
        'jiter',
        'tiktoken',
        # ASGI server chain (gateway only; the API fn runs as a plain handler)
        'uvicorn',
        'uvloop',
        # app-only heavy chain (never in the gateway)
        'psycopg_binary',
        'sqlalchemy',
        'pdfminer',
        'PIL',
    )
    for package in packages:
        (deps / package).mkdir(parents=True)
        (deps / package / '__init__.py').write_text('', encoding='utf-8')
    for dist_info in ('litellm-1.80.5.dist-info', 'psycopg_binary-3.2.10.dist-info'):
        (deps / dist_info).mkdir()
        (deps / dist_info / 'METADATA').write_text('', encoding='utf-8')
    return deps


def _zip_names(archive_path: Path) -> set[str]:
    with zipfile.ZipFile(archive_path) as archive:
        return set(archive.namelist())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_application_package_is_rooted_at_finsight(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """The archive root holds finsight/ directly so the CDK handler imports."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )

    names = _zip_names(output / 'api.zip')
    assert 'finsight/__init__.py' in names
    assert 'finsight/core/app.py' in names
    assert not any(name.startswith('src/') for name in names), names


def test_config_travels_beside_the_package(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """config/ is a sibling of finsight/ so the loader resolves it at runtime."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )

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


def test_junk_files_are_excluded(source_tree: Path, deps_dir: Path, tmp_path: Path) -> None:
    """OS and bytecode junk never reaches the archive."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )

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
    build_lambda_module.build_lambda(output, source_root=source_tree, package='api')

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


def test_default_build_produces_both_packages(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """The deploy pipeline needs api.zip and gateway.zip, each with a checksum."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(output, source_root=source_tree, deps_dir=deps_dir)

    names = sorted(path.name for path in output.iterdir())
    assert names == ['api.zip', 'api.zip.sha256', 'gateway.zip', 'gateway.zip.sha256']
    assert (output / 'gateway.zip.sha256').read_text(encoding='utf-8').endswith('  gateway.zip\n')


def test_api_package_excludes_litellm_chain(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """The API zip drops the litellm chain so the vendored set fits the quota."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )

    names = _zip_names(output / 'api.zip')
    for prefix in ('litellm/', 'openai/', 'jiter/', 'tiktoken/', 'uvicorn/', 'uvloop/'):
        assert not any(name.startswith(prefix) for name in names), prefix
    assert not any(name.startswith('litellm-') for name in names), 'litellm dist-info leaked'
    # The API surface still keeps the shared runtime.
    assert 'fastapi/__init__.py' in names
    assert 'boto3/__init__.py' in names
    assert 'tokenizers/__init__.py' in names


def test_gateway_package_carries_litellm_chain_and_bridge(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """The gateway zip keeps litellm + the ASGI chain and drops app-only heavies."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='gateway'
    )

    names = _zip_names(output / 'gateway.zip')
    for prefix in ('litellm/', 'openai/', 'uvicorn/', 'tokenizers/'):
        assert any(name.startswith(prefix) for name in names), prefix
    for prefix in (
        'psycopg_binary/',
        'psycopg_binary.libs/',
        'pillow.libs/',
        'uvloop/',
        'sqlalchemy/',
        'pdfminer/',
        'PIL/',
    ):
        assert not any(name.startswith(prefix) for name in names), prefix
    assert not any(name.startswith('psycopg_binary-') for name in names), 'dist-info leaked'
    # The bridge: app source, config, and the Web Adapter startup command.
    assert 'finsight/__init__.py' in names
    assert 'config/schema.yaml' in names
    assert 'run.sh' in names
    with zipfile.ZipFile(output / 'gateway.zip') as archive:
        run_sh_mode = archive.getinfo('run.sh').external_attr >> 16
    assert run_sh_mode & 0o111, 'run.sh must be executable'


def test_gateway_run_sh_boots_uvicorn_on_port(
    source_tree: Path, deps_dir: Path, tmp_path: Path
) -> None:
    """The startup command runs uvicorn on the adapter-provided PORT."""
    output = tmp_path / 'out'
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='gateway'
    )

    with zipfile.ZipFile(output / 'gateway.zip') as archive:
        run_sh = archive.read('run.sh').decode('utf-8')

    assert 'uvicorn finsight.entrypoints.gateway.app:app' in run_sh
    assert 'PORT' in run_sh


def test_unzipped_size_gate_fails_loudly(source_tree: Path, deps_dir: Path, tmp_path: Path) -> None:
    """A package over the 250 MB unzipped Lambda quota aborts the build."""
    output = tmp_path / 'out'
    # Give the archive some unzipped weight so the tiny limit trips.
    (deps_dir / 'fastapi' / '__init__.py').write_bytes(b'x' * 4096)
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )

    with pytest.raises(SystemExit, match='exceeds the'):
        build_lambda_module._enforce_unzipped_size(output / 'api.zip', limit_mb=0.001)

    # The real gate runs as part of every build and passes for small packages.
    build_lambda_module.build_lambda(
        output, source_root=source_tree, deps_dir=deps_dir, package='api'
    )


def test_vendoring_runs_once_for_both_packages(
    source_tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deps are vendored once and reused for both packages."""
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
    assert (output / 'api.zip').exists()
    assert (output / 'gateway.zip').exists()
    assert not (output / 'deps').exists()
