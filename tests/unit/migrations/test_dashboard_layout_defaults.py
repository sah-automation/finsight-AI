"""Tests for the default-layout resolution in the dashboard_layouts migration.

``scripts/run_migration.py`` sets only VECTOR_DB_* variables, so the full
config profile cannot be resolved on the documented production migration path.
The migration must bake the documented schema defaults with a warning there,
while failing loudly when a profile loads but has no dashboard section.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / 'migrations' / 'versions'


def _load_migration() -> Any:
    name = 'migration_0009_dashboard_layouts'
    spec = importlib.util.spec_from_file_location(
        name, MIGRATIONS_DIR / '0009_dashboard_layouts.py'
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


def test_env_only_path_bakes_documented_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """A loader failure (VECTOR_DB_* only) falls back, as env.py and 0008 do."""

    def unusable() -> Any:
        raise RuntimeError('Required environment variable not set: ANSWER_CACHE_TABLE')

    monkeypatch.setattr(migration, 'load_config', unusable)

    assert migration._default_layout() == migration._DEFAULT_LAYOUT


def test_profile_without_dashboard_section_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(migration, 'load_config', lambda: SimpleNamespace(dashboard=None))

    with pytest.raises(RuntimeError, match='dashboard config section is required'):
        migration._default_layout()


def test_active_profile_supplies_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    chart = SimpleNamespace(chart_id='revenue_trend', span='full')
    dashboard = SimpleNamespace(
        default_layout=SimpleNamespace(kpi_codes=['revenue'], charts=[chart])
    )
    monkeypatch.setattr(migration, 'load_config', lambda: SimpleNamespace(dashboard=dashboard))

    assert migration._default_layout() == {
        'kpi_codes': ['revenue'],
        'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}],
    }
