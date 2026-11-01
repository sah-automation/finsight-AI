"""Smoke imports ensuring every public module is importable."""

from __future__ import annotations

import importlib
import pkgutil

import finsight


def test_all_modules_import() -> None:
    failures: list[tuple[str, str]] = []
    for mod in pkgutil.walk_packages(finsight.__path__, prefix='finsight.'):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001 - pragma: no cover - surfaced as assertion failure
            failures.append((mod.name, repr(exc)))
    assert not failures, failures[:5]
