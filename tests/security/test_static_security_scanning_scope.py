"""Baseline guardrails for static security scanning (issue #80)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parents[2]

pytestmark = pytest.mark.security


def _detect_secrets_hook() -> dict:
    config = yaml.safe_load((PROJECT_ROOT / '.pre-commit-config.yaml').read_text())
    for repo in config['repos']:
        for hook in repo.get('hooks', []):
            if hook.get('id') == 'detect-secrets':
                return hook
    raise AssertionError('detect-secrets hook not found')


class TestStaticSecurityScanningScope:
    def test_bandit_config_is_present(self) -> None:
        pyproject = (PROJECT_ROOT / 'pyproject.toml').read_text()
        assert '[tool.bandit]' in pyproject

    def test_semgrep_config_is_present(self) -> None:
        assert (PROJECT_ROOT / '.semgrep.yml').exists()

    def test_security_scan_workflow_exists(self) -> None:
        assert (PROJECT_ROOT / '.github' / 'workflows' / 'security-scan.yml').exists()

    def test_advanced_quality_workflow_runs_security_tools(self) -> None:
        workflow = (
            PROJECT_ROOT / '.github' / 'workflows' / 'advanced-quality-gates.yml'
        ).read_text()
        assert 'bandit' in workflow
        assert 'pip-audit' in workflow or 'pip_audit' in workflow
        assert 'trivy' in workflow.lower()

    def test_secrets_are_scanned_in_tests(self) -> None:
        hook = _detect_secrets_hook()
        exclude = str(hook.get('exclude', ''))
        assert 'tests/' not in exclude

    def test_docs_describe_security_scanning_frequency(self) -> None:
        docs = (PROJECT_ROOT / 'docs' / 'advanced-quality-gates.md').read_text()
        assert 'security' in docs.lower()
        assert 'scheduled' in docs.lower() or 'manual' in docs.lower()
