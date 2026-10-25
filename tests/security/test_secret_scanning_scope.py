"""Guardrails for the secret-scanning scope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.security

PROJECT_ROOT = Path(__file__).parents[2]


def _detect_secrets_hook() -> dict[str, Any]:
    config = yaml.safe_load((PROJECT_ROOT / '.pre-commit-config.yaml').read_text())
    for repo in config['repos']:
        for hook in repo.get('hooks', []):
            if hook.get('id') == 'detect-secrets':
                return hook
    raise AssertionError('detect-secrets hook not found')


class TestSecretScanningScope:
    """Tests must be scanned by the same detect-secrets hook as production code."""

    def test_pre_commit_does_not_exclude_tests(self) -> None:
        hook = _detect_secrets_hook()
        exclude = str(hook.get('exclude', ''))

        assert '^tests/' not in exclude
        assert 'tests/' not in exclude

    def test_make_secrets_uses_the_same_hook(self) -> None:
        makefile = (PROJECT_ROOT / 'Makefile').read_text()

        assert 'pre-commit run detect-secrets --all-files' in makefile

    def test_ci_security_job_runs_the_security_suite(self) -> None:
        workflow = (PROJECT_ROOT / '.github/workflows/ci.yml').read_text()

        assert 'pytest tests/security' in workflow
        assert '-m "security"' in workflow
        assert '-k "security' not in workflow
