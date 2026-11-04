"""Unit tests for the exception-freshness gate helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.architecture.test_invariants import (
    _commit_files,
    _current_ticket_number,
    _git,
    _latest_commit_touching,
    _parse_exception_items,
    _references_ticket,
    _working_tree_changed_files,
)


class TestParseExceptionItems:
    """Tests for _parse_exception_items."""

    def test_parses_file_exceptions(self) -> None:
        text = """
OVERSIZED_FILE_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py': {
        'reason': 'Reason here',
        'owner': 'owner',
        'removal_condition': 'Remove when done',
    },
}
OVERSIZED_FUNCTION_EXCEPTIONS = {}
"""
        items = _parse_exception_items(text)
        assert items == [('path/to/file.py', 'Remove when done')]

    def test_parses_function_exceptions(self) -> None:
        text = """
OVERSIZED_FILE_EXCEPTIONS = {}
OVERSIZED_FUNCTION_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py::func_name': {
        'reason': 'Reason here',
        'owner': 'owner',
        'removal_condition': 'Remove when done #123',
    },
}
OVERSIZED_PRIVATE_FUNCTION_EXCEPTIONS = {}
"""
        items = _parse_exception_items(text)
        assert items == [('path/to/file.py', 'Remove when done #123')]

    def test_parses_private_function_exceptions(self) -> None:
        text = """
OVERSIZED_FILE_EXCEPTIONS = {}
OVERSIZED_FUNCTION_EXCEPTIONS = {}
OVERSIZED_PRIVATE_FUNCTION_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py::_private_func': {
        'reason': 'Reason here',
        'owner': 'owner',
        'removal_condition': 'Split the helper',
    },
}
"""
        items = _parse_exception_items(text)
        assert items == [('path/to/file.py', 'Split the helper')]

    def test_deduplicates_entries(self) -> None:
        text = """
OVERSIZED_FILE_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py': {
        'reason': 'Reason 1',
        'owner': 'owner',
        'removal_condition': 'Remove when done',
    },
}
OVERSIZED_FUNCTION_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py::func': {
        'reason': 'Reason 2',
        'owner': 'owner',
        'removal_condition': 'Remove when done',
    },
}
OVERSIZED_PRIVATE_FUNCTION_EXCEPTIONS = {}
"""
        items = _parse_exception_items(text)
        # Should deduplicate by (relative, removal_condition)
        assert len(items) == 1
        assert items[0] == ('path/to/file.py', 'Remove when done')

    def test_handles_missing_removal_condition(self) -> None:
        text = """
OVERSIZED_FILE_EXCEPTIONS: dict[str, dict[str, str]] = {
    'path/to/file.py': {
        'reason': 'Reason here',
        'owner': 'owner',
    },
}
OVERSIZED_FUNCTION_EXCEPTIONS = {}
"""
        items = _parse_exception_items(text)
        assert items == [('path/to/file.py', '')]

    def test_returns_empty_for_empty_text(self) -> None:
        items = _parse_exception_items('')
        assert items == []


class TestCurrentTicketNumber:
    """Tests for _current_ticket_number."""

    def test_reads_from_check_exception_freshness_pr(self) -> None:
        with patch.dict(os.environ, {'CHECK_EXCEPTION_FRESHNESS_PR': '42'}):
            assert _current_ticket_number(Path('test')) == '42'

    def test_reads_from_github_pr_number(self) -> None:
        with patch.dict(os.environ, {'GITHUB_PR_NUMBER': '123'}):
            assert _current_ticket_number(Path('test')) == '123'

    def test_reads_from_pr_number(self) -> None:
        with patch.dict(os.environ, {'PR_NUMBER': '999'}):
            assert _current_ticket_number(Path('test')) == '999'

    def test_reads_from_github_ref(self) -> None:
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/pull/555/merge'}):
            assert _current_ticket_number(Path('test')) == '555'

    def test_reads_from_github_head_ref(self) -> None:
        with patch.dict(os.environ, {'GITHUB_HEAD_REF': 'feature-123-fix'}):
            assert _current_ticket_number(Path('test')) == '123'

    def test_reads_from_github_ref_name(self) -> None:
        with patch.dict(os.environ, {'GITHUB_REF_NAME': 'pr-777'}):
            assert _current_ticket_number(Path('test')) == '777'

    def test_reads_from_git_commit_message(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = 'Fix issue #456'
            mock_git.return_value = mock_result
            assert _current_ticket_number(Path('test')) == '456'

    def test_reads_from_git_branch_name(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = 'feature/789-new-feature'
            mock_git.return_value = mock_result
            assert _current_ticket_number(Path('test')) == '789'

    def test_returns_none_when_no_ticket_found(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = 'no ticket here'
            mock_git.return_value = mock_result
            assert _current_ticket_number(Path('test')) is None

    def test_ignores_non_numeric_env_values(self) -> None:
        with patch.dict(os.environ, {'CHECK_EXCEPTION_FRESHNESS_PR': 'abc'}):
            assert _current_ticket_number(Path('test')) is None


class TestReferencesTicket:
    """Tests for _references_ticket."""

    def test_matches_exact_number(self) -> None:
        assert _references_ticket('Remove when #123 is done', '123') is True

    def test_matches_number_with_word_boundaries(self) -> None:
        assert _references_ticket('Related to issue #456', '456') is True

    def test_does_not_match_partial(self) -> None:
        assert _references_ticket('Related to issue #1234', '123') is False

    def test_does_not_match_in_other_numbers(self) -> None:
        assert _references_ticket('See #12345', '123') is False

    def test_case_sensitive(self) -> None:
        assert _references_ticket('Ticket #ABC', 'abc') is False


class TestWorkingTreeChangedFiles:
    """Tests for _working_tree_changed_files."""

    def test_returns_changed_files_from_diff(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            # First call: diff --name-only HEAD
            result1 = MagicMock()
            result1.stdout = 'src/file1.py\nsrc/file2.py\n'
            # Second call: diff --cached --name-only
            result2 = MagicMock()
            result2.stdout = ''
            # Third call: status --porcelain
            result3 = MagicMock()
            result3.stdout = ''
            mock_git.side_effect = [result1, result2, result3]

            changed = _working_tree_changed_files()
            assert changed == {'src/file1.py', 'src/file2.py'}

    def test_returns_staged_files(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            result1 = MagicMock()
            result1.stdout = ''
            result2 = MagicMock()
            result2.stdout = 'src/staged.py\n'
            result3 = MagicMock()
            result3.stdout = ''
            mock_git.side_effect = [result1, result2, result3]

            changed = _working_tree_changed_files()
            assert changed == {'src/staged.py'}

    def test_returns_untracked_files_from_status(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            result1 = MagicMock()
            result1.stdout = ''
            result2 = MagicMock()
            result2.stdout = ''
            result3 = MagicMock()
            result3.stdout = '?? src/new.py\n M src/modified.py\n'
            mock_git.side_effect = [result1, result2, result3]

            changed = _working_tree_changed_files()
            assert changed == {'src/new.py', 'src/modified.py'}

    def test_handles_renames(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            result1 = MagicMock()
            result1.stdout = ''
            result2 = MagicMock()
            result2.stdout = ''
            result3 = MagicMock()
            result3.stdout = 'R  src/old.py -> src/new.py\n'
            mock_git.side_effect = [result1, result2, result3]

            changed = _working_tree_changed_files()
            assert changed == {'src/new.py'}

    def test_returns_empty_when_no_changes(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            result = MagicMock()
            result.stdout = ''
            mock_git.return_value = result

            changed = _working_tree_changed_files()
            assert changed == set()


class TestGitHelpers:
    """Tests for git helper functions."""

    def test_git_returns_completed_process(self) -> None:
        result = _git('status')
        assert isinstance(result, subprocess.CompletedProcess)
        assert hasattr(result, 'stdout')
        assert hasattr(result, 'returncode')

    def test_latest_commit_touching_returns_sha(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = 'abc123def\n'  # pragma: allowlist secret
            mock_git.return_value = mock_result

            sha = _latest_commit_touching('src/finsight/some_file.py')
            assert sha == 'abc123def'  # pragma: allowlist secret

    def test_latest_commit_touching_returns_none_for_missing_file(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = ''
            mock_git.return_value = mock_result

            sha = _latest_commit_touching('nonexistent.py')
            assert sha is None

    def test_commit_files_returns_changed_files(self) -> None:
        with patch('tests.architecture.test_invariants._git') as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = 'src/file1.py\nsrc/file2.py\n'
            mock_git.return_value = mock_result

            files = _commit_files('abc123')
            assert files == {'src/file1.py', 'src/file2.py'}
