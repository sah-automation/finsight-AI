#!/usr/bin/env python3
"""Check that relative Markdown links resolve.

Scans the hand-written documentation files and fails on a missing target.
External links (http, https, mailto) and pure anchors are ignored.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATHS = ('README.md', 'CONTRIBUTING.md', 'GLOSSARY.md', 'SECURITY.md', 'docs')
LINK_PATTERN = re.compile(r'!?\[[^\]]*]\(([^)]+)\)')
IGNORED_PREFIXES = ('http://', 'https://', 'mailto:', '#')


def _markdown_files() -> list[Path]:
    files: list[Path] = []
    for relative in SCAN_PATHS:
        path = REPO_ROOT / relative
        if path.is_dir():
            files.extend(sorted(path.rglob('*.md')))
        elif path.is_file():
            files.append(path)
    return files


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding='utf-8')
    for match in LINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        if target.startswith(IGNORED_PREFIXES):
            continue
        # Drop an optional title and any anchor.
        target = target.split()[0].split('#', maxsplit=1)[0]
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f'{path.relative_to(REPO_ROOT)}: missing {target}')
    return errors


def main() -> int:
    """Return a non-zero exit status when any relative link is broken."""
    errors: list[str] = []
    for path in _markdown_files():
        errors.extend(_check_file(path))
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Checked relative links in {len(_markdown_files())} Markdown files')
    return 0


if __name__ == '__main__':
    sys.exit(main())
