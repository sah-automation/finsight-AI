"""Regression test for deprecated asyncio event-loop access (issue #134)."""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / 'src' / 'finsight'

DEPRECATED_PATTERNS = (
    'get_event_loop',
    'run_until_complete',
)


def test_no_deprecated_event_loop_access() -> None:
    """Fail if deprecated event-loop access reappears in source code."""
    offenders: list[str] = []
    for path in SRC_ROOT.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for pattern in DEPRECATED_PATTERNS:
            if pattern in text:
                offenders.append(f'{path}:{pattern}')
    assert not offenders, 'Deprecated event-loop access found:\n' + '\n'.join(offenders)
