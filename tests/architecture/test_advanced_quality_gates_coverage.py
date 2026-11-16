"""Meta-tests for the advanced quality gates (issue #80)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PROPERTY_CANDIDATE_DIRS = [
    ROOT / 'property',
]
MUTATION_CANDIDATE_DIRS = [ROOT / 'mutmut']
SECURITY_CANDIDATE_DIRS = [ROOT / 'security']

# Genuine workflows that should exist after pruning scaffolding duplicates
GENUINE_WORKFLOWS = [
    'ci.yml',
    'web.yml',
    'openapi.yml',
    'aws-role-smoke.yml',
    'golden-live.yml',
    'security-scan.yml',
    'advanced-quality-gates.yml',
]


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

    def test_genuine_workflows_exist(self) -> None:
        workflows_dir = ROOT.parent / '.github' / 'workflows'
        for wf in GENUINE_WORKFLOWS:
            assert (workflows_dir / wf).exists(), f'genuine workflow missing: {wf}'

    def test_no_scaffolding_workflows_remain(self) -> None:
        """Ensure byte-identical scaffolding stubs have been removed."""
        workflows_dir = ROOT.parent / '.github' / 'workflows'
        scaffolding_names = {
            'advanced-quality.yml',
            'quality-gates.yml',
            'container-scan.yml',
            'dependency-scan.yml',
            'hypothesis.yml',
            'infra-scan.yml',
            'mutation-testing.yml',
            'mutation.yml',
            'mutmut.yml',
            'property-tests.yml',
            'property.yml',
            'sast.yml',
            'security-scanning.yml',
            'static-security-scan.yml',
            'static-security.yml',
            'load.yml',
            'load-performance.yml',
            'perf.yml',
            'performance.yml',
        }
        for wf in scaffolding_names:
            assert not (workflows_dir / wf).exists(), f'scaffolding workflow still present: {wf}'

    def test_mutmut_config_exists(self) -> None:
        pyproject = (ROOT.parent / 'pyproject.toml').read_text()
        assert '[tool.mutmut]' in pyproject

    def test_bandit_config_exists(self) -> None:
        pyproject = (ROOT.parent / 'pyproject.toml').read_text()
        assert '[tool.bandit]' in pyproject
