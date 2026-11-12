"""Unit import smoke for modules referenced by infrastructure."""

from __future__ import annotations

import importlib

import pytest

from tests.support.infra_reference_scan import (
    INFRA_REFERENCE_ALLOWLIST,
    handler_mismatch_exists,
    scan_infra_references,
)


@pytest.mark.parametrize('module_name', sorted(scan_infra_references()))
def test_infra_referenced_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


def test_allowlist_recorded() -> None:
    assert INFRA_REFERENCE_ALLOWLIST


def test_main_handler_mismatch_is_resolved() -> None:
    # Issue #287 made the CDK-declared handler resolvable.
    assert handler_mismatch_exists() is False
