#!/usr/bin/env python3
"""Build the Lambda zip packages for the API and the model gateway.

Two archives come out of this script (Stage D-2, issue #330):

- ``api.zip`` — the API function: the application source rooted at ``finsight/``
  so the CDK handler ``finsight.entrypoints.api.main.handler`` imports from the
  Lambda task root, ``config/`` beside it, and the vendored runtime dependencies
  minus the litellm chain (with ``llm_transport=remote_gateway`` the API calls
  the gateway over the network instead of importing litellm).
- ``gateway.zip`` — the model-gateway function: the full litellm chain plus the
  FastAPI/uvicorn bridge. It runs behind the AWS Lambda Web Adapter, so the
  archive also carries ``run.sh`` (the startup command the function's handler
  points at).

Each archive is deterministic: every entry carries a fixed timestamp and the
dependency set is pinned by ``uv.lock``, so a rebuild from the same inputs is
byte-identical. A sha256 checksum is written next to each archive so the deploy
pipeline can verify the artifacts it uploads, and an unzipped-size gate fails
the build loudly when a package would exceed the 250 MB Lambda quota.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Bundle paths are (source path relative to the repo root, archive path) pairs.
# ``src/finsight`` lands at the archive root as ``finsight/`` so the CDK handler
# resolves from the Lambda task root, with ``config/`` as its sibling
# (the config loader walks up from the package or falls back to the working
# directory, both of which are the task root at runtime).
BUNDLE_PATHS: tuple[tuple[str, str], ...] = (
    ('src/finsight', 'finsight'),
    ('config', 'config'),
)
EXCLUDED_DIRS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo'}
EXCLUDED_NAMES = {'.DS_Store'}

# Fixed timestamp keeps the archive byte-for-byte reproducible.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# Lambda runs x86_64 Linux on Python 3.12. Wheels are selected for that
# platform so a locally synthesized package matches the one CI deploys.
LAMBDA_PLATFORM = 'x86_64-unknown-linux-gnu'
LAMBDA_PYTHON_VERSION = '3.12'

# Hard Lambda deployment-package quota, checked on the *unzipped* contents.
LAMBDA_UNZIPPED_LIMIT_MB = 250

# Top-level vendored packages excluded from both archives: never imported by
# either runtime (the OTLP path is HTTP/protobuf, not gRPC — issue #276).
SHARED_TRIMMED_DEPS: frozenset[str] = frozenset(
    {
        'aiobotocore',
        'fastavro',
        'grpc',
        'grpcio',
        'grpcio_status',
        'google',
        'googleapis_common_protos',
        'opentelemetry_exporter_otlp_proto_grpc',
    }
)

# api.zip drops the litellm chain (remote_gateway transport), the ASGI server
# chain (the API function is a plain Lambda handler), and the aiohttp chain
# that only litellm/aiobotocore pull in.
API_EXCLUDED_DEPS: frozenset[str] = SHARED_TRIMMED_DEPS | {
    'litellm',
    'openai',
    'jiter',
    'tiktoken',
    'aiohttp',
    'frozenlist',
    'multidict',
    'propcache',
    'yarl',
    'uvicorn',
    'uvloop',
    'httptools',
    'watchfiles',
    'websockets',
}

# gateway.zip keeps litellm and the ASGI chain but drops the application-only
# heavy packages (document processing, Aurora/DynamoDB drivers, et al) plus the
# wheel data dirs and loop accelerators of packages that are not shipped.
GATEWAY_EXCLUDED_DEPS: frozenset[str] = SHARED_TRIMMED_DEPS | {
    'sqlalchemy',
    'alembic',
    'asyncpg',
    'psycopg',
    'psycopg2',
    'psycopg_binary',
    'psycopg_pool',
    'psycopg_binary.libs',
    'pgvector',
    'pdfplumber',
    'pdfminer',
    'pypdfium2',
    'pypdfium2_raw',
    'PIL',
    'pillow.libs',
    'pytesseract',
    'pdf2image',
    'docx',
    'openpyxl',
    'et_xmlfile',
    'redis',
    'lxml',
    'faker',
    'email_validator',
    'python_multipart',
    'greenlet',
    'uvloop',
}

# Startup command for the Lambda Web Adapter (function handler = 'run.sh').
GATEWAY_RUN_SH = """#!/bin/bash
set -euo pipefail
exec python -m uvicorn finsight.entrypoints.gateway.app:app \\
  --host 0.0.0.0 --port "${PORT:-8080}"
"""

PACKAGE_EXCLUSIONS: dict[str, frozenset[str]] = {
    'api': API_EXCLUDED_DEPS,
    'gateway': GATEWAY_EXCLUDED_DEPS,
}


def _collect_files(source_root: Path) -> list[tuple[Path, str]]:
    """Return (absolute path, archive name) pairs, in a stable order."""
    files: list[tuple[Path, str]] = []
    for relative, archive_root in BUNDLE_PATHS:
        root = source_root / relative
        if not root.is_dir():
            raise FileNotFoundError(f'Missing bundle path: {root}')
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.name in EXCLUDED_NAMES:
                continue
            if EXCLUDED_DIRS.intersection(path.parts):
                continue
            archive_name = (Path(archive_root) / path.relative_to(root)).as_posix()
            files.append((path, archive_name))
    return files


def _runtime_deps_commands(requirements_file: Path, deps_dir: Path) -> list[list[str]]:
    """Return the uv commands that vendor the locked runtime dependencies."""
    export = [
        'uv',
        'export',
        '--frozen',
        '--no-dev',
        '--no-emit-project',
        '--format',
        'requirements-txt',
        '--output-file',
        str(requirements_file),
    ]
    install = [
        'uv',
        'pip',
        'install',
        '--no-deps',
        '--no-compile',
        '--python-platform',
        LAMBDA_PLATFORM,
        '--python-version',
        LAMBDA_PYTHON_VERSION,
        '--target',
        str(deps_dir),
        '--requirements',
        str(requirements_file),
    ]
    return [export, install]


def _vendor_runtime_deps(deps_dir: Path) -> None:
    """Install the locked runtime dependency set into ``deps_dir``."""
    deps_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        requirements_file = Path(scratch) / 'runtime-requirements.txt'
        for command in _runtime_deps_commands(requirements_file, deps_dir):
            # Command vectors are fixed by _runtime_deps_commands (no shell, no
            # user input) — the same pattern as verify_aws_cli_permissions.py.
            subprocess.run(command, check=True, cwd=REPO_ROOT)  # noqa: S603


def _top_level_name(archive_name: str) -> str:
    """Map an archive entry to its vendored top-level package name.

    ``litellm/__init__.py`` and ``litellm-1.80.5.dist-info/METADATA`` both map
    to ``litellm`` so exclusions cover code and metadata directories alike.
    """
    top = archive_name.split('/', 1)[0]
    if top.endswith('.dist-info'):
        top = top[: -len('.dist-info')].rsplit('-', 1)[0]
    return top


def _is_excluded(archive_name: str, excluded: frozenset[str]) -> bool:
    return _top_level_name(archive_name) in excluded


def _add_file(archive: zipfile.ZipFile, path: Path, archive_name: str) -> None:
    """Add one file under a fixed timestamp so rebuilds are reproducible."""
    info = zipfile.ZipInfo(archive_name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, path.read_bytes())


def _add_tree(archive: zipfile.ZipFile, root: Path, excluded: frozenset[str] = frozenset()) -> None:
    """Add every file under ``root`` flattened at the archive root."""
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        if path.name in EXCLUDED_NAMES:
            continue
        if EXCLUDED_DIRS.intersection(path.parts):
            continue
        archive_name = path.relative_to(root).as_posix()
        if excluded and _is_excluded(archive_name, excluded):
            continue
        _add_file(archive, path, archive_name)


def _add_run_sh(archive: zipfile.ZipFile) -> None:
    """Add the executable startup command the Web Adapter executes."""
    info = zipfile.ZipInfo('run.sh', ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o755 << 16
    archive.writestr(info, GATEWAY_RUN_SH)


def _write_package(output_dir: Path, source_root: Path, deps_dir: Path, package: str) -> Path:
    """Write one package zip (no checksum, no gate — see build_lambda)."""
    excluded = PACKAGE_EXCLUSIONS[package]
    archive_path = output_dir / f'{package}.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        _add_tree(archive, deps_dir, excluded)
        for path, archive_name in _collect_files(source_root):
            _add_file(archive, path, archive_name)
        if package == 'gateway':
            _add_run_sh(archive)
    return archive_path


def _enforce_unzipped_size(archive_path: Path, limit_mb: int = LAMBDA_UNZIPPED_LIMIT_MB) -> None:
    """Fail the build loudly when a package exceeds the Lambda unzipped quota."""
    with zipfile.ZipFile(archive_path) as archive:
        total_bytes = sum(info.file_size for info in archive.infolist())
    if total_bytes > limit_mb * 1024 * 1024:
        raise SystemExit(
            f'{archive_path.name}: {total_bytes / 1048576:.1f} MB unzipped exceeds the '
            f'{limit_mb} MB Lambda deployment-package quota. Trim the package lists in '
            'scripts/build_lambda.py before deploying.'
        )


def build_lambda(
    output_dir: Path,
    source_root: Path = REPO_ROOT,
    deps_dir: Path | None = None,
    package: str = 'all',
) -> list[Path]:
    """Build the requested package(s) and their checksums, returning zip paths.

    Runtime dependencies are vendored from the frozen lockfile once and reused
    for every package, unless ``deps_dir`` is supplied, in which case that
    directory's contents are flattened into the archive roots instead (used by
    tests). ``package`` is ``'api'``, ``'gateway'``, or ``'all'``.
    """
    if package not in ('api', 'gateway', 'all'):
        raise ValueError(f"Unknown package {package!r}; expected 'api', 'gateway', or 'all'")
    packages = ('api', 'gateway') if package == 'all' else (package,)

    output_dir.mkdir(parents=True, exist_ok=True)
    staging_deps = output_dir / 'deps'
    cleanup_deps = deps_dir is None
    if deps_dir is None:
        shutil.rmtree(staging_deps, ignore_errors=True)
        _vendor_runtime_deps(staging_deps)
        deps_dir = staging_deps

    archive_paths = []
    for name in packages:
        archive_path = _write_package(output_dir, source_root, deps_dir, name)
        _enforce_unzipped_size(archive_path)
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        archive_path.with_suffix('.zip.sha256').write_text(
            f'{digest}  {archive_path.name}\n', encoding='utf-8'
        )
        archive_paths.append(archive_path)
        print(f'Built {archive_path} ({archive_path.stat().st_size} bytes)')

    if cleanup_deps:
        shutil.rmtree(staging_deps, ignore_errors=True)
    return archive_paths


def main() -> int:
    """Parse arguments and build the package(s)."""
    parser = argparse.ArgumentParser(description='Build the Lambda zip package(s)')
    parser.add_argument('--output', default='dist/lambda', help='Output directory')
    parser.add_argument(
        '--package',
        choices=('api', 'gateway', 'all'),
        default='all',
        help='Which package to build (default: both)',
    )
    args = parser.parse_args()

    build_lambda(Path(args.output), package=args.package)
    return 0


if __name__ == '__main__':
    sys.exit(main())
