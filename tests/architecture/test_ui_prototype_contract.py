"""Static contract for the user-supplied UI prototype delivered under issue #349."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE = ROOT / 'prototype'
STANDARDS = ROOT / 'UI_STANDARDS.md'

REQUIRED_FILES = (
    'README.md',
    'styles.css',
    'shell.js',
    'charts.js',
    'login.html',
    'ask.html',
    'documents.html',
    'upload.html',
    'dashboard.html',
    'charts.html',
    'reports.html',
    'settings.html',
    'not-allowed.html',
)
SCREENS = tuple(name for name in REQUIRED_FILES if name.endswith('.html'))
USER_ADDED_SCREENS = ('reports.html', 'not-allowed.html')
FOCUS_ORDER_MARKER = 'Accessibility: focus order'
NO_BUILD_ARTIFACTS = (
    'package.json',
    'package-lock.json',
    'pnpm-lock.yaml',
    'tsconfig.json',
    'vite.config.js',
    'vite.config.ts',
    'node_modules',
)


def test_prototype_contains_the_expected_delivery_files() -> None:
    """Every screen and shared asset named by the ticket is present."""
    assert PROTOTYPE.is_dir(), 'prototype/ must exist at the repository root'
    missing = sorted(name for name in REQUIRED_FILES if not (PROTOTYPE / name).is_file())
    assert missing == []


def test_prototype_needs_no_build_step() -> None:
    """The screens stay openable as plain files, not as an application project."""
    present = sorted(name for name in NO_BUILD_ARTIFACTS if (PROTOTYPE / name).exists())
    assert present == []


@pytest.mark.parametrize('screen', SCREENS)
def test_screen_is_standalone_html(screen: str) -> None:
    """Each screen is a complete HTML document using the shared stylesheet."""
    text = (PROTOTYPE / screen).read_text(encoding='utf-8')
    assert text.lstrip().lower().startswith('<!doctype html>')
    assert 'href="styles.css"' in text


@pytest.mark.parametrize('screen', SCREENS)
def test_screen_has_accessibility_annotations(screen: str) -> None:
    """ARIA annotations and explicit focus-order notes accompany every screen."""
    text = (PROTOTYPE / screen).read_text(encoding='utf-8')
    assert 'aria-' in text, f'{screen} needs an ARIA annotation'
    assert FOCUS_ORDER_MARKER in text, f'{screen} needs a focus-order note'


def test_readme_documents_viewing_conventions_and_additions() -> None:
    """The README explains how to view the prototype and records user additions."""
    readme = (PROTOTYPE / 'README.md').read_text(encoding='utf-8').lower()
    for phrase in (
        'no build step',
        'open',
        'browser',
        'conventions',
        'focus order',
        'loading',
        'error',
        'empty',
        'disabled',
        'user-added screens',
        *USER_ADDED_SCREENS,
    ):
        assert phrase in readme, f'README must mention {phrase!r}'


def test_standards_point_to_the_binding_root_prototype() -> None:
    """UI_STANDARDS follows the parent decision that root prototype/ is binding."""
    text = STANDARDS.read_text(encoding='utf-8')
    assert '`prototype/`' in text
    assert 'docs/plans/ui/prototype/' not in text
    for screen in USER_ADDED_SCREENS:
        assert screen in text, f'UI_STANDARDS must mention {screen}'
