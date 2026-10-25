"""Guard tests for the import-linter configuration itself."""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SRC_ROOT = PROJECT_ROOT / 'src' / 'finsight'
CONTRACT_KEYS = ('source_modules', 'forbidden_modules', 'modules')


def _load_contracts() -> list[dict[str, object]]:
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as handle:
        config = tomllib.load(handle)
    return config['tool']['importlinter']['contracts']


def _referenced_modules(contracts: list[dict[str, object]]) -> set[str]:
    modules: set[str] = set()
    for contract in contracts:
        for key in CONTRACT_KEYS:
            values = contract.get(key, [])
            if isinstance(values, list):
                modules.update(value for value in values if isinstance(value, str))
    return modules


def _is_covered(package: str, referenced: set[str]) -> bool:
    return any(module == package or module.startswith(f'{package}.') for module in referenced)


def _top_level_packages() -> list[str]:
    return sorted(
        f'finsight.{path.name}'
        for path in SRC_ROOT.iterdir()
        if path.is_dir() and (path / '__init__.py').exists()
    )


class TestImportContractsCoverPackages:
    """A new package must not silently escape the import contracts."""

    def test_every_top_level_package_is_referenced(self) -> None:
        referenced = _referenced_modules(_load_contracts())

        uncovered = [
            package for package in _top_level_packages() if not _is_covered(package, referenced)
        ]

        assert not uncovered, (
            'Top-level packages missing from import-linter contracts: '
            f'{uncovered}. Add a forbidden or independence contract.'
        )

    def test_coverage_helper_detects_an_unknown_package(self) -> None:
        referenced = _referenced_modules(_load_contracts())

        assert _is_covered('finsight.core', referenced)
        assert not _is_covered('finsight.newlayer', referenced)

    def test_every_adapter_is_in_the_independence_contract(self) -> None:
        independence = [
            contract for contract in _load_contracts() if contract.get('type') == 'independence'
        ]

        assert len(independence) == 1, 'Exactly one adapter independence contract is expected'
        listed = set(independence[0].get('modules', []))
        adapters = {
            f'finsight.adapters.{path.name}'
            for path in (SRC_ROOT / 'adapters').iterdir()
            if path.is_dir() and (path / '__init__.py').exists()
        }

        assert adapters <= listed, (
            f'Adapters missing from independence contract: {adapters - listed}'
        )

    def test_only_composition_may_import_adapters(self) -> None:
        contracts = _load_contracts()
        inner_layers = {'finsight.domain', 'finsight.application', 'finsight.entrypoints'}
        inner_layers.add('finsight.core')

        for package in inner_layers:
            contracts_for_package = [
                contract for contract in contracts if contract.get('source_modules') == [package]
            ]
            forbidden = set().union(
                *(set(contract.get('forbidden_modules', [])) for contract in contracts_for_package)
            )
            assert 'finsight.adapters' in forbidden, (
                f'{package} must forbid importing finsight.adapters'
            )
