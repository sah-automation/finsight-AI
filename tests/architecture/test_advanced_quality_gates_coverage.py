"""Meta-tests for the advanced quality gates (issue #80)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PROPERTY_CANDIDATE_DIRS = [
    ROOT / 'property',
    ROOT / 'properties',
    ROOT / 'property_based',
    ROOT / 'hypothesis',
    ROOT / 'unit' / 'property',
    ROOT / 'unit' / 'properties',
]
MUTATION_CANDIDATE_DIRS = [ROOT / 'mutation', ROOT / 'mutmut', ROOT / 'mutation_testing']
SECURITY_CANDIDATE_DIRS = [ROOT / 'security']


def _dirs(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


@pytest.mark.architecture
class TestAdvancedQualityGatesCoverage:
    def test_property_suite_directory_exists(self) -> None:
        assert _dirs(PROPERTY_CANDIDATE_DIRS), 'expected property-based test directory'

    def test_property_harness_or_tests_exist(self) -> None:
        assert any(list(base.glob('test_*.py')) for base in _dirs(PROPERTY_CANDIDATE_DIRS))

    def test_mutation_suite_directory_exists(self) -> None:
        assert _dirs(MUTATION_CANDIDATE_DIRS), 'expected mutation test directory'

    def test_mutation_tests_are_non_placeholder(self) -> None:
        for base in _dirs(MUTATION_CANDIDATE_DIRS):
            assert list(base.glob('test_*.py')), f'mutation suite must contain tests: {base}'

    def test_security_scanning_scope_test_exists(self) -> None:
        security_dir = ROOT / 'security'
        assert any(security_dir.glob('*security*scanning*.py')) or any(
            security_dir.glob('*static*security*.py')
        )

    def test_advanced_quality_workflow_exists(self) -> None:
        assert (ROOT.parent / '.github' / 'workflows' / 'advanced-quality-gates.yml').exists()

    def test_mutmut_config_exists(self) -> None:
        pyproject = (ROOT.parent / 'pyproject.toml').read_text()
        assert '[tool.mutmut]' in pyproject

    def test_bandit_config_exists(self) -> None:
        pyproject = (ROOT.parent / 'pyproject.toml').read_text()
        assert '[tool.bandit]' in pyproject
