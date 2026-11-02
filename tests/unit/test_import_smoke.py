"""Smoke imports ensuring every public module is importable."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import finsight


def test_all_modules_import() -> None:
    failures: list[tuple[str, str]] = []
    for mod in pkgutil.walk_packages(finsight.__path__, prefix='finsight.'):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001 - pragma: no cover - surfaced as assertion failure
            failures.append((mod.name, repr(exc)))
    assert not failures, failures[:5]


from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / 'src'


def _all_source_packages() -> list[str]:
    packages: set[str] = set()
    base = SRC_ROOT / 'finsight'
    for init_file in base.rglob('__init__.py'):
        relative = init_file.parent.relative_to(SRC_ROOT)
        packages.add('.'.join(relative.parts))
    return sorted(packages)


def _package_smoke(package: str) -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    try:
        imported_package = importlib.import_module(package)
    except Exception as exc:  # noqa: BLE001
        return [(package, repr(exc))]
    if not hasattr(imported_package, '__path__'):
        return failures
    for module in pkgutil.walk_packages(imported_package.__path__, prefix=f'{package}.'):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001
            failures.append((module.name, repr(exc)))
    return failures


@pytest.mark.parametrize('package', _all_source_packages())
def test_package_imports(package: str) -> None:
    failures = _package_smoke(package)
    assert not failures, failures[:5]


@pytest.mark.parametrize('package', _all_source_packages())
def test_package_import_smoke(package: str) -> None:
    failures = _package_smoke(package)
    assert not failures, failures[:5]


@pytest.mark.parametrize('package', _all_source_packages())
def test_per_package_import_smoke(package: str) -> None:
    failures = _package_smoke(package)
    assert not failures, failures[:5]
