"""Baseline guardrails for mutation testing (issue #80)."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.mutation
class TestMutationBaselineScope:
    def test_mutmut_config_exists(self) -> None:
        pyproject = (PROJECT_ROOT / 'pyproject.toml').read_text()
        assert '[tool.mutmut]' in pyproject
        assert 'paths_to_mutate' in pyproject

    def test_mutation_workflow_exists(self) -> None:
        assert (PROJECT_ROOT / '.github' / 'workflows' / 'mutation.yml').exists()

    def test_makefile_has_mutation_target(self) -> None:
        makefile = (PROJECT_ROOT / 'Makefile').read_text()
        assert '\nmutation:' in makefile or 'mutation:' in makefile
