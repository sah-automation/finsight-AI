# Switch Coverage Tests
# Ensures every config switch has both paths tested.
# Run with: pytest tests/unit/switches -v --tb=short -m switch

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from finsight.core.config.models import SwitchesConfig

# ============================================================
# Switch Coverage Meta-Test
# ============================================================

# Each config switch must have a dedicated test file. The file is expected to
# contain a test for the ON path and a test for the OFF path.
SWITCH_TO_TEST_FILE = {
    'reranker_enabled': 'test_reranker_switch.py',
    'backup_request_enabled': 'test_backup_request_switch.py',
    'parallel_retrieval_enabled': 'test_parallel_retrieval_switch.py',
    'per_sentence_citation_check': 'test_citation_check_switch.py',
    'async_textract_enabled': 'test_textract_switch.py',
    'ocr_fallback_enabled': 'test_ocr_fallback_switch.py',
    'answer_cache_enabled': 'test_answer_cache_switch.py',
    'role_cache_enabled': 'test_role_cache_switch.py',
    'detailed_tracing_enabled': 'test_tracing_switch.py',
    'usage_metering_enabled': 'test_metering_switch.py',
}


@pytest.mark.switch
class TestSwitchCoverage:
    """Meta-test: every switch field must have a corresponding test file."""

    def test_all_switches_have_test_files(self) -> None:
        """Every field in SwitchesConfig must have a test file."""
        missing = []
        for field in SwitchesConfig.model_fields:
            test_file = SWITCH_TO_TEST_FILE.get(field)
            if test_file is None:
                missing.append(f'{field}: no test mapping defined')
                continue
            if not (Path(__file__).parent / test_file).exists():
                missing.append(f'{field}: missing {test_file}')

        assert not missing, (
            'Switch coverage gaps:\n'
            + '\n'.join(f'  {gap}' for gap in missing)
            + '\n\nEach switch must have both ON and OFF paths tested.'
        )

    def test_test_files_map_to_real_switches(self) -> None:
        """Mapped test files must not reference removed switches."""
        known_fields = set(SwitchesConfig.model_fields)
        stale = sorted(set(SWITCH_TO_TEST_FILE) - known_fields)
        assert not stale, 'Switch test mapping references unknown switches:\n' + '\n'.join(
            f'  {name}' for name in stale
        )

    def test_each_file_has_on_and_off_paths(self) -> None:
        """Each switch test file must define an ON and an OFF test."""
        incomplete = []
        for switch, test_file in SWITCH_TO_TEST_FILE.items():
            path = Path(__file__).parent / test_file
            if not path.exists():
                continue  # Covered by test_all_switches_have_test_files.
            tree = ast.parse(path.read_text(), filename=str(path))
            test_names = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith('test_')
            }
            has_on = any(name.endswith('_on') for name in test_names)
            has_off = any(name.endswith('_off') for name in test_names)
            if not (has_on and has_off):
                incomplete.append(f'{switch}: {test_file} (on={has_on}, off={has_off})')

        assert not incomplete, 'Switch test files missing ON or OFF path:\n' + '\n'.join(
            f'  {item}' for item in incomplete
        )
