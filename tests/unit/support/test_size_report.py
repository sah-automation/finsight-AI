"""Tests for the ``make sizes`` helper."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.size_report import (
    MAX_FILE_LINES,
    MAX_PRIVATE_FUNCTION_LINES,
    MAX_PUBLIC_FUNCTION_LINES,
    analyze,
    build_report,
    large_files,
    large_private_functions,
    large_public_functions,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def _function(name: str, body_lines: int) -> str:
    body = ''.join(f'    value_{index} = {index}\n' for index in range(body_lines))
    return f'def {name}():\n{body}    return value_0\n'


def _build_fixture_tree(root: Path) -> None:
    _write(root / 'small.py', 'def small():\n    return 1\n')
    _write(
        root / 'big.py',
        '# padding\n' * (MAX_FILE_LINES + 1)
        + _function('public_long', MAX_PUBLIC_FUNCTION_LINES + 1)
        + _function('_private_long', MAX_PRIVATE_FUNCTION_LINES + 1),
    )


def test_thresholds_match_the_architecture_ratchet() -> None:
    assert (MAX_FILE_LINES, MAX_PUBLIC_FUNCTION_LINES, MAX_PRIVATE_FUNCTION_LINES) == (300, 30, 60)


def test_analyze_reports_each_size_bucket(tmp_path: Path) -> None:
    _build_fixture_tree(tmp_path)

    report = analyze(tmp_path)

    assert [path.name for path, _ in report['files']] == ['big.py']
    assert [name for _, name, _ in report['public_functions']] == ['public_long']
    assert [name for _, name, _ in report['private_functions']] == ['_private_long']
    assert report['file_threshold'] == MAX_FILE_LINES
    assert report['public_threshold'] == MAX_PUBLIC_FUNCTION_LINES
    assert report['private_threshold'] == MAX_PRIVATE_FUNCTION_LINES


def test_thresholds_filter_files_and_functions(tmp_path: Path) -> None:
    _build_fixture_tree(tmp_path)

    assert [path.name for path, _ in large_files(tmp_path, threshold=MAX_FILE_LINES)] == ['big.py']
    assert large_files(tmp_path, threshold=10_000) == []
    assert [name for _, name, _ in large_public_functions(tmp_path, threshold=2)] == ['public_long']
    assert [name for _, name, _ in large_private_functions(tmp_path, threshold=2)] == [
        '_private_long'
    ]


def test_build_report_uses_configured_thresholds(tmp_path: Path) -> None:
    _build_fixture_tree(tmp_path)

    report = build_report(analyze(tmp_path, file_threshold=5), base=tmp_path)

    assert 'Files over 5 lines' in report
    assert 'Public functions over 30 lines' in report
    assert 'Private functions over 60 lines' in report
    assert 'big.py' in report
    assert 'small.py' not in report


def test_build_report_marks_empty_sections(tmp_path: Path) -> None:
    _write(tmp_path / 'small.py', 'def small():\n    return 1\n')

    report = build_report(analyze(tmp_path), base=tmp_path)

    assert report.count('(none)') == 3


def test_analyze_skips_unparseable_files(tmp_path: Path) -> None:
    _write(tmp_path / 'broken.py', 'def broken(:\n')

    report = analyze(tmp_path)

    assert report['files'] == []
    assert report['public_functions'] == []
    assert report['private_functions'] == []
