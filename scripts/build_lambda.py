#!/usr/bin/env python3
"""Build the Lambda zip package for the API function.

This is the DI-21 packaging scaffold. It bundles the application package and
`config/` into a deterministic zip. Third-party dependencies are not vendored
yet; that remains part of DI-21 (see the implementation plan, section 17).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_PATHS = ('src/finsight', 'config')
EXCLUDED_DIRS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo'}

# Fixed timestamp keeps the archive byte-for-byte reproducible.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _bundle_files() -> list[Path]:
    """Return the files to include, in a stable order."""
    files: list[Path] = []
    for relative in BUNDLE_PATHS:
        root = REPO_ROOT / relative
        if not root.is_dir():
            raise FileNotFoundError(f'Missing bundle path: {relative}')
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if EXCLUDED_DIRS.intersection(path.parts):
                continue
            files.append(path)
    return files


def _add_file(archive: zipfile.ZipFile, path: Path) -> None:
    """Add one file with a fixed timestamp so rebuilds are reproducible."""
    info = zipfile.ZipInfo(path.relative_to(REPO_ROOT).as_posix(), ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, path.read_bytes())


def build_lambda(output_dir: Path) -> Path:
    """Build the package and its checksum, returning the zip path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / 'api.zip'

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in _bundle_files():
            _add_file(archive, path)

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
