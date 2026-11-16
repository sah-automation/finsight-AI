#!/usr/bin/env python3
"""Build the Lambda zip package for the API function.

The archive is a complete deployment package (Stage D-2): the application
source rooted at ``finsight/`` so the CDK handler
``finsight.entrypoints.api.main.handler`` imports from the Lambda task root,
``config/`` beside it, and the vendored runtime dependencies installed from the
frozen lockfile into the archive root.

The build is deterministic: every entry carries a fixed timestamp and the
dependency set is pinned by ``uv.lock``, so a rebuild from the same inputs is
byte-identical. A sha256 checksum is written next to the archive so the deploy
pipeline can verify the artifact it uploads.
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
# ``src/finsight`` lands at the archive root as ``finsight/`` so the CDK
# handler resolves from the Lambda task root, with ``config/`` as its sibling
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


def _add_file(archive: zipfile.ZipFile, path: Path, archive_name: str) -> None:
    """Add one file under a fixed timestamp so rebuilds are reproducible."""
    info = zipfile.ZipInfo(archive_name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, path.read_bytes())


def _add_tree(archive: zipfile.ZipFile, root: Path) -> None:
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
        _add_file(archive, path, path.relative_to(root).as_posix())


def build_lambda(
    output_dir: Path, source_root: Path = REPO_ROOT, deps_dir: Path | None = None
) -> Path:
    """Build the package and its checksum, returning the zip path.

    Runtime dependencies are vendored from the frozen lockfile unless
    ``deps_dir`` is supplied, in which case that directory's contents are
    flattened into the archive root instead (used by tests).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    staging_deps = output_dir / 'deps'
    cleanup_deps = deps_dir is None
    if deps_dir is None:
        shutil.rmtree(staging_deps, ignore_errors=True)
        _vendor_runtime_deps(staging_deps)
        deps_dir = staging_deps

    archive_path = output_dir / 'api.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        _add_tree(archive, deps_dir)
        for path, archive_name in _collect_files(source_root):
            _add_file(archive, path, archive_name)

    if cleanup_deps:
        shutil.rmtree(staging_deps, ignore_errors=True)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(
        f'{digest}  {archive_path.name}\n', encoding='utf-8'
    )

    print(f'Built {archive_path} ({archive_path.stat().st_size} bytes)')
    return archive_path


def main() -> int:
    """Parse arguments and build the package."""
    parser = argparse.ArgumentParser(description='Build the Lambda zip package')
    parser.add_argument('--output', default='dist/lambda', help='Output directory')
    args = parser.parse_args()

    build_lambda(Path(args.output))
    return 0


if __name__ == '__main__':
    sys.exit(main())
