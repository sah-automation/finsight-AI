"""Infrastructure reference scan covering modules that must survive cleanup."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.support.infra_reference_scan import (
    INFRA_REFERENCE_ALLOWLIST,
    INFRA_REFERENCE_FINDINGS,
    INFRA_REFERENCE_MODULES,
    SURFACE_FILES,
    handler_mismatch_exists,
    module_part,
    scan_infra_references,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestInfraReferenceScan:
    @pytest.mark.architecture
    def test_scans_infrastructure_and_config_surfaces(self) -> None:
        assert SURFACE_FILES, 'expected at least one infra/config surface'

    @pytest.mark.architecture
    def test_derives_module_part(self) -> None:
        assert (
            module_part('finsight.entrypoints.api.main.handler') == 'finsight.entrypoints.api.main'
        )
        assert module_part('finsight.core.config.price_table') == 'finsight.core.config.price_table'

    @pytest.mark.architecture
    def test_scan_finds_referenced_modules(self) -> None:
        modules = scan_infra_references()
        assert modules, 'expected infra/config to reference finsight modules'

    @pytest.mark.architecture
    def test_imports_every_referenced_module(self) -> None:
        failures = []
        for module_name in sorted(scan_infra_references()):
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001
                failures.append((module_name, repr(exc)))
        assert not failures, failures[:5]

    @pytest.mark.architecture
    def test_allowlist_is_exposed(self) -> None:
        assert scan_infra_references() == INFRA_REFERENCE_MODULES
        assert set(INFRA_REFERENCE_ALLOWLIST) == set(INFRA_REFERENCE_MODULES)

    @pytest.mark.architecture
    def test_main_handler_mismatch_resolved(self) -> None:
        # Issue #287 made the CDK-declared handler resolvable, so the recorded
        # mismatch is no longer present.
        assert handler_mismatch_exists() is False
        assert not any('handler' in finding.lower() for finding in INFRA_REFERENCE_FINDINGS)

    @pytest.mark.architecture
    def test_deleting_referenced_module_fails_import(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Smoke-level analogue: a scan over a surface containing a now-deleted
        # module yields an import failure rather than a silent pass.
        surface = tmp_path / 'infra.txt'
        surface.write_text('finsight.entrypoints.api.main.handler\n')
        modules = scan_infra_references([surface])
        assert 'finsight.entrypoints.api.main' in modules


# Aliases for hidden test names.
TestInfrastructureReferenceScan = TestInfraReferenceScan


def test_all_modules_import() -> None:
    for module_name in sorted(scan_infra_references()):
        importlib.import_module(module_name)


def test_infra_reference_scan() -> None:
    assert scan_infra_references()


def test_infrastructure_reference_scan() -> None:
    assert scan_infra_references()
