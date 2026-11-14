from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]

pytestmark = pytest.mark.mutation


class TestMutmutBaselineScope:
    def test_mutmut_config_exists(self) -> None:
        pyproject = (PROJECT_ROOT / 'pyproject.toml').read_text()
        assert '[tool.mutmut]' in pyproject

    def test_mutation_workflow_exists(self) -> None:
        assert (PROJECT_ROOT / '.github' / 'workflows' / 'mutation.yml').exists()

    def test_makefile_has_mutation_target(self) -> None:
        makefile = (PROJECT_ROOT / 'Makefile').read_text()
        assert 'mutation:' in makefile
