"""Report source files and functions that exceed the project size limits.

This module backs ``make sizes``.  It scans ``src/finsight`` and uses the same
line-counting rules as ``tests/architecture/test_invariants.py``.

Thresholds (the project ratchet enforced by the architecture tests):

* files: more than 300 lines
* public functions: more than 30 lines
* private (single-underscore) functions: more than 60 lines
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.support.ast_inspection import find_function_defs, get_python_files

SRC_ROOT = PROJECT_ROOT / 'src' / 'finsight'

MAX_FILE_LINES = 300
MAX_PUBLIC_FUNCTION_LINES = 30
MAX_PRIVATE_FUNCTION_LINES = 60


class _SizeReport(TypedDict):
    root: Path
    file_threshold: int
    public_threshold: int
    private_threshold: int
    files: list[tuple[Path, int]]
    public_functions: list[tuple[Path, str, int]]
    private_functions: list[tuple[Path, str, int]]


def count_lines(path: Path | str) -> int:
    """Count lines the same way the architecture tests do."""
    return Path(path).read_text(encoding='utf-8').count('\n')


def _is_private_name(name: str) -> bool:
    return name.startswith('_') and not name.startswith('__')


def _all_function_rows(root: Path) -> list[tuple[Path, str, int]]:
    rows: list[tuple[Path, str, int]] = []
    for path in get_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for name, start, end in find_function_defs(tree):
            rows.append((path, name, end - start + 1))
    return rows


def large_files(
    root: Path | str | None = None, threshold: int = MAX_FILE_LINES
) -> list[tuple[Path, int]]:
    """Return Python files above *threshold* lines."""
    target = SRC_ROOT if root is None else Path(root)
    rows: list[tuple[Path, int]] = []
    for path in get_python_files(target):
        lines = count_lines(path)
        if lines > threshold:
            rows.append((path, lines))
    return sorted(rows, key=lambda item: (-item[1], str(item[0])))


def large_public_functions(
    root: Path | str | None = None, threshold: int = MAX_PUBLIC_FUNCTION_LINES
) -> list[tuple[Path, str, int]]:
    """Return public (non-underscore) functions above *threshold* lines."""
    target = SRC_ROOT if root is None else Path(root)
    return sorted(
        (
            (path, name, lines)
            for path, name, lines in _all_function_rows(target)
            if not name.startswith('_') and lines > threshold
        ),
        key=lambda item: (-item[2], str(item[0]), item[1]),
    )


def large_private_functions(
    root: Path | str | None = None, threshold: int = MAX_PRIVATE_FUNCTION_LINES
) -> list[tuple[Path, str, int]]:
    """Return single-underscore private functions above *threshold* lines."""
    target = SRC_ROOT if root is None else Path(root)
    return sorted(
        (
            (path, name, lines)
            for path, name, lines in _all_function_rows(target)
            if _is_private_name(name) and lines > threshold
        ),
        key=lambda item: (-item[2], str(item[0]), item[1]),
    )


def analyze(root: Path | str | None = None, file_threshold: int = MAX_FILE_LINES) -> _SizeReport:
    """Collect all three size reports for *root*."""
    target = SRC_ROOT if root is None else Path(root)
    return {
        'root': target,
        'file_threshold': file_threshold,
        'public_threshold': MAX_PUBLIC_FUNCTION_LINES,
        'private_threshold': MAX_PRIVATE_FUNCTION_LINES,
        'files': large_files(target, file_threshold),
        'public_functions': large_public_functions(target, MAX_PUBLIC_FUNCTION_LINES),
        'private_functions': large_private_functions(target, MAX_PRIVATE_FUNCTION_LINES),
    }


def build_report(
    data: _SizeReport | None = None,
    root: Path | str | None = None,
    base: Path | None = None,
) -> str:
    """Render *data* as the text printed by ``make sizes``."""
    if data is None:
        data = analyze(root)
    if base is None:
        base = PROJECT_ROOT

    def display(path: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    lines: list[str] = []

    file_header = f'Files over {data["file_threshold"]} lines'
    lines.append(file_header)
    lines.append('=' * len(file_header))
    files = data['files']
    if not files:
        lines.append('(none)')
    else:
        for path, n in files:
            lines.append(f'{display(path)}: {n} lines')

    lines.append('')
    public_header = f'Public functions over {data["public_threshold"]} lines'
    lines.append(public_header)
    lines.append('=' * len(public_header))
    public = data['public_functions']
    if not public:
        lines.append('(none)')
    else:
        for path, name, n in public:
            lines.append(f'{display(path)}::{name}: {n} lines')

    lines.append('')
    private_header = f'Private functions over {data["private_threshold"]} lines'
    lines.append(private_header)
    lines.append('=' * len(private_header))
    private = data['private_functions']
    if not private:
        lines.append('(none)')
    else:
        for path, name, n in private:
            lines.append(f'{display(path)}::{name}: {n} lines')

    lines.append('')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Report oversized source files and functions.')
    parser.add_argument('--root', type=Path, default=SRC_ROOT, help='Root directory to scan.')
    parser.add_argument(
        '--threshold-file',
        type=int,
        default=MAX_FILE_LINES,
        help='File line threshold (default: 300).',
    )
    args = parser.parse_args(argv)

    if args.threshold_file <= 0:
        parser.error('--threshold-file must be a positive integer')
    if not args.root.exists():
        parser.error(f'--root does not exist: {args.root}')

    report = analyze(args.root, args.threshold_file)
    print(build_report(report, args.root, PROJECT_ROOT), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
