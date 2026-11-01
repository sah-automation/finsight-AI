"""Architecture checks for metered paid-call coverage (issue #137).

Every paid provider primitive may only be touched by its adapter module or by
the composition decorator stacks, which wrap it with a ``Metered*`` decorator.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).parent.parent.parent / 'src' / 'finsight'
BASE_PAID_ADAPTERS = {
    'LiteLLMGateway',
    'LiteLLMEmbedding',
    'CohereReranker',
    'TextractReader',
}

# Modules that are allowed to mention base paid adapters directly.
ALLOWED_FILES = {
    'adapters/llm/lite_llm_gateway.py',
    'adapters/llm/__init__.py',
    'adapters/embedding/lite_llm_embedding.py',
    'adapters/embedding/__init__.py',
    'adapters/rerank/cohere_reranker.py',
    'adapters/rerank/__init__.py',
    'adapters/readers/textract_reader.py',
    'adapters/readers/__init__.py',
    'composition/adapter_stacks.py',
    'composition/_adapter_stacks_extraction.py',
    'composition/reader_registry.py',
    'composition/container.py',
}


def _relative(path: Path) -> str:
    return str(path.relative_to(SRC_ROOT)).replace('\\', '/')


@pytest.mark.architecture
class TestPaidCallMeteringCoverage:
    def test_no_business_code_imports_paid_adapters(self) -> None:
        violations: list[str] = []
        for pkg in ('domain', 'application', 'entrypoints'):
            root = SRC_ROOT / pkg
            for filepath in root.rglob('*.py'):
                try:
                    tree = ast.parse(filepath.read_text())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    names: set[str] = set()
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            names.add(alias.name.rsplit('.', 1)[-1])
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        for alias in node.names:
                            names.add(alias.name)
                    if names & BASE_PAID_ADAPTERS:
                        rel = _relative(filepath)
                        if rel not in ALLOWED_FILES:
                            violations.append(f'{rel}:{node.lineno}')
        assert not violations, (
            'Paid adapters referenced outside approved surfaces:\\n' + '\\n'.join(violations)
        )

    def test_composition_stacks_use_metering_decorators(self) -> None:
        text = (SRC_ROOT / 'composition' / 'adapter_stacks.py').read_text() + (
            SRC_ROOT / 'composition' / '_adapter_stacks_extraction.py'
        ).read_text()
        for decorator in ('MeteredLLM', 'MeteredEmbedding', 'MeteredReranker', 'MeteredExtraction'):
            assert decorator in text

    def test_base_llm_self_records_usage_row(self) -> None:
        text = (SRC_ROOT / 'adapters' / 'llm' / '_llm_gateway_usage.py').read_text()
        assert '_record_usage' in text
        assert "'service': 'llm'" in text

    def test_base_embedding_self_records_usage_row(self) -> None:
        text = (SRC_ROOT / 'adapters' / 'embedding' / '_embedding_operations.py').read_text()
        assert '_record_usage' in text
        assert "'service': 'embedding'" in text
