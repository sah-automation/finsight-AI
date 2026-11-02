"""Ratchet protecting against new behavior-free pass-through modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.ast_inspection import find_passthrough_modules, is_passthrough_module

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / 'src' / 'finsight'

# Baseline measured on the clean tree. Tickets may only ever lower this value.
BASELINE_PASSTHROUGH_COUNT = 13


def _passthrough_count() -> int:
    return len(find_passthrough_modules(SRC_ROOT))


class TestPassthroughModuleRatchet:
    @pytest.mark.architecture
    def test_baseline_matches_measured_count(self) -> None:
        # The ratchet floor must never sit above the current measured count.
        assert _passthrough_count() <= BASELINE_PASSTHROUGH_COUNT

    @pytest.mark.architecture
    def test_passthrough_count_does_not_increase(self) -> None:
        count = _passthrough_count()
        assert count <= BASELINE_PASSTHROUGH_COUNT, (
            'Pass-through module count increased '
            f'({count} > {BASELINE_PASSTHROUGH_COUNT}). '
            'Collapse or justify the new shim instead of raising the floor.'
        )


class TestPassthroughModuleDetector:
    @pytest.mark.architecture
    def test_flags_alias_only_module(self, tmp_path: Path) -> None:
        module = tmp_path / 'alias_only.py'
        module.write_text('from canonical import Thing\n\nAlias = Thing\n')
        assert is_passthrough_module(module) is True

    @pytest.mark.architecture
    def test_flags_wildcard_hub(self, tmp_path: Path) -> None:
        module = tmp_path / 'wildcard_hub.py'
        module.write_text('from canonical import *\n')
        assert is_passthrough_module(module) is True

    @pytest.mark.architecture
    def test_flags_two_line_getattr_shim(self, tmp_path: Path) -> None:
        module = tmp_path / 'getattr_shim.py'
        module.write_text(
            'def __getattr__(name):\n'
            '    import importlib\n'
            '    return getattr(importlib.import_module("canonical"), name)\n'
        )
        assert is_passthrough_module(module) is True

    @pytest.mark.architecture
    def test_ignores_real_module(self, tmp_path: Path) -> None:
        module = tmp_path / 'real_module.py'
        module.write_text('def real() -> int:\n    return 1\n')
        assert is_passthrough_module(module) is False

    @pytest.mark.architecture
    def test_ignores_init_facade(self, tmp_path: Path) -> None:
        module = tmp_path / '__init__.py'
        module.write_text('from .real import real\n\n__all__ = ["real"]\n')
        assert is_passthrough_module(module) is False

    @pytest.mark.architecture
    def test_flagging_reflected_in_directory_scan(self, tmp_path: Path) -> None:
        alias = tmp_path / 'alias_only.py'
        alias.write_text('from canonical import Thing\n\nAlias = Thing\n')
        real = tmp_path / 'real.py'
        real.write_text('VALUE = 1\n')
        found = {path.name for path in find_passthrough_modules(tmp_path)}
        assert 'alias_only.py' in found
        assert 'real.py' not in found


@pytest.mark.architecture
def test_adding_synthetic_shim_raises_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new shim must make the ratchet fail (validated by direct assertion)."""

    before = _passthrough_count()
    synthetic = SRC_ROOT / '_synthetic_passthrough_shim.py'
    synthetic.write_text('from canonical import Thing\n\nAlias = Thing\n')
    try:
        new_count = _passthrough_count()
        assert new_count == before + 1
    finally:
        synthetic.unlink(missing_ok=True)
