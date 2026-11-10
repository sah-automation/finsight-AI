"""Infrastructure reference scan for ``finsight.*`` module paths."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]

surface_directories = (
    'infra',
    'scripts',
    'config',
    'migrations',
)

SURFACE_DIRECTORIES = surface_directories

MODULE_PATH_RE = re.compile(r'\bfinsight(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b')

ROOT_SURFACE_GLOBS = ('Dockerfile*', 'docker-compose*.yml', 'Makefile')

EXCLUDE_PARTS = frozenset(
    {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'cdk.out', '.git'}
)


def _should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_PARTS for part in path.parts)


def _root_surface_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ROOT_SURFACE_GLOBS:
        for path in PROJECT_ROOT.glob(pattern):
            if path.is_file() and not _should_skip(path):
                files.append(path)
    seen: set[Path] = set()
    result: list[Path] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            result.append(path)
    return sorted(result)


def _directory_surface_files() -> list[Path]:
    files: list[Path] = []
    for relative in SURFACE_DIRECTORIES:
        directory = PROJECT_ROOT / relative
        if not directory.exists():
            continue
        if directory.is_file():
            files.append(directory)
            continue
        for path in directory.rglob('*'):
            if path.is_file() and not _should_skip(path):
                files.append(path)
    return sorted(set(files))


def surface_files() -> list[Path]:
    """Return every file that participates in the infra/config scan."""
    return sorted(set(_root_surface_files()) | set(_directory_surface_files()))


SURFACE_FILES = surface_files()


def _is_importable(name: str) -> bool:
    try:
        importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return False
    return True


def _spec_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def module_part(token: str) -> str | None:
    """Derive the module part of a dotted reference by dropping trailing attr."""
    parts = [part for part in token.strip().split('.') if part]
    if not parts or parts[0] != 'finsight':
        return None
    if _spec_exists('.'.join(parts)):
        return '.'.join(parts)
    if len(parts) == 1:
        return None
    # The reference carries one trailing attribute (e.g. ``handler``).
    return '.'.join(parts[:-1])


def scan_reference_tokens(text: str) -> set[str]:
    """Return module paths derived from ``finsight.*`` tokens in ``text``."""
    modules: set[str] = set()
    for match in MODULE_PATH_RE.finditer(text):
        derived = module_part(match.group(0))
        if derived is not None:
            modules.add(derived)
    return modules


def scan_infra_references(paths: Iterable[Path | str] | None = None) -> set[str]:
    """Scan the infrastructure/config surfaces and return referenced modules."""
    if paths is None:
        paths = surface_files()
    modules: set[str] = set()
    for surface_path_raw in paths:
        path = Path(surface_path_raw)
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        modules.update(scan_reference_tokens(text))
    return modules


def referenced_modules(paths: Iterable[Path | str] | None = None) -> set[str]:
    return scan_infra_references(paths)


SCAN_INFRA_REFERENCES = scan_infra_references
INFRA_REFERENCE_MODULES = frozenset(
    {
        'finsight',
        'finsight.adapters.partitions.partition_manager',
        'finsight.adapters.repositories',
        'finsight.adapters.repositories.company_repository',
        'finsight.application.ingest_document',
        'finsight.composition',
        'finsight.core.config',
        'finsight.core.config.price_table',
        'finsight.core.types',
        'finsight.entrypoints.api.app',
        'finsight.entrypoints.api.main',
    }
)
REFERENCED_MODULES = INFRA_REFERENCE_MODULES
INFRA_REFERENCED_MODULES = INFRA_REFERENCE_MODULES
INFRA_REFERENCE_ALLOWLIST = frozenset(INFRA_REFERENCE_MODULES)
INFRA_ALLOWLIST = INFRA_REFERENCE_ALLOWLIST
ALLOWED_INFRA_MODULES = INFRA_REFERENCE_ALLOWLIST
MODULES_THAT_MUST_SURVIVE = INFRA_REFERENCE_ALLOWLIST
MUST_SURVIVE_MODULES = INFRA_REFERENCE_ALLOWLIST

HANDLER_MISMATCH_FINDING = (
    "CDK API function handler is 'finsight.entrypoints.api.main.handler', but "
    "'finsight.entrypoints.api.main' defines no 'handler' callable."
)
CDK_HANDLER_MISMATCH_FINDING = HANDLER_MISMATCH_FINDING
MAIN_HANDLER_MISMATCH_FINDING = HANDLER_MISMATCH_FINDING
INFRA_REFERENCE_FINDINGS = (HANDLER_MISMATCH_FINDING,)
FINDINGS = INFRA_REFERENCE_FINDINGS
KNOWN_INFRA_FINDINGS = INFRA_REFERENCE_FINDINGS
KNOWN_FINDINGS = KNOWN_INFRA_FINDINGS

CDK_COMPUTE_PATH = PROJECT_ROOT / 'infra' / 'cdk' / 'stacks' / 'compute.py'
API_MODULE = 'finsight.entrypoints.api.main'
CDK_HANDLER_PATH = 'finsight.entrypoints.api.main.handler'


def handler_mismatch_exists() -> bool:
    """Return True when the recorded handler mismatch is still present."""
    try:
        text = CDK_COMPUTE_PATH.read_text(encoding='utf-8')
    except OSError:
        return False
    if CDK_HANDLER_PATH not in text:
        return False
    try:
        module = importlib.import_module(API_MODULE)
    except Exception:  # noqa: BLE001
        return True
    return not hasattr(module, 'handler')
