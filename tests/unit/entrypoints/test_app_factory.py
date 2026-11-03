"""Tests for the FastAPI application factory and its provider wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.entrypoints.api import app as app_module
from finsight.entrypoints.api import main as main_module

if TYPE_CHECKING:
    import pytest


def test_create_app_initialises_providers_with_the_built_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = object()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(app_module, 'load_config', lambda: None)
    monkeypatch.setattr(app_module, 'build_container', lambda *_args, **_kwargs: container)
    monkeypatch.setattr(
        app_module.providers,
        'init',
        lambda value: captured.setdefault('value', value),
    )

    app_module.create_app()

    assert captured['value'] is container


def test_main_exposes_app_on_first_access(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    monkeypatch.setattr(main_module, '_get_app', lambda: sentinel)

    assert main_module.app is sentinel
