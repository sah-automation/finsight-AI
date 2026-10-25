"""Regression tests proving the architecture helpers can actually fail."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.support.ast_inspection import (
    find_folders_missing_readme,
    find_forbidden_constructor_calls,
    find_methods_without_company_id,
    get_all_calls,
    is_property_decorator,
)

if TYPE_CHECKING:
    from pathlib import Path


def _parse(code: str) -> ast.Module:
    return ast.parse(code)


class TestPropertyDecoratorDetection:
    """@property detection must inspect decorator expressions, not ast.Decorator."""

    def test_detects_property_decorator(self) -> None:
        tree = _parse('@property\ndef value(self):\n    return 1\n')
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        assert is_property_decorator(function.decorator_list[0])

    def test_detects_qualified_property_decorator(self) -> None:
        tree = _parse('@builtins.property\ndef value(self):\n    return 1\n')
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        assert is_property_decorator(function.decorator_list[0])

    def test_ignores_other_decorators(self) -> None:
        tree = _parse('@staticmethod\ndef value():\n    return 1\n')
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        assert not is_property_decorator(function.decorator_list[0])


class TestCompanyIdScanner:
    """The company_id scanner must catch missing parameters and skip properties."""

    def test_flags_method_without_company_id(self, tmp_path: Path) -> None:
        package = tmp_path / 'repositories'
        package.mkdir()
        (package / 'repository.py').write_text(
            'class Repository:\n'
            '    def get_document(self, document_id: str) -> str:\n'
            '        return document_id\n'
        )

        violations = find_methods_without_company_id(package)

        assert len(violations) == 1
        assert violations[0][1] == 'get_document'

    def test_accepts_method_with_company_id(self, tmp_path: Path) -> None:
        package = tmp_path / 'repositories'
        package.mkdir()
        (package / 'repository.py').write_text(
            'class Repository:\n'
            '    def get_document(self, company_id: str, document_id: str) -> str:\n'
            '        return document_id\n'
        )

        assert find_methods_without_company_id(package) == []

    def test_skips_property_methods(self, tmp_path: Path) -> None:
        package = tmp_path / 'repositories'
        package.mkdir()
        (package / 'repository.py').write_text(
            'class Repository:\n'
            '    @property\n'
            '    def get_label(self) -> str:\n'
            "        return 'label'\n"
        )

        assert find_methods_without_company_id(package) == []


class TestCallScanner:
    """Call extraction must keep fully dotted names for constructor rules."""

    def test_extracts_dotted_call_names(self) -> None:
        tree = _parse("boto3.client('s3')\nhttpx.Client()\nlitellm.completion()\nOpenAI()\n")

        names = {name for name, _ in get_all_calls(tree)}

        assert names == {'boto3.client', 'httpx.Client', 'litellm.completion', 'OpenAI'}

    def test_flags_forbidden_constructor(self, tmp_path: Path) -> None:
        package = tmp_path / 'application'
        package.mkdir()
        (package / 'flow.py').write_text("import boto3\n\nboto3.client('s3')\n")

        violations = find_forbidden_constructor_calls(package)

        assert [name for _, name, _ in violations] == ['boto3.client']


class TestReadmeScanner:
    """The README check must include the package root itself."""

    def test_flags_root_without_readme(self, tmp_path: Path) -> None:
        root = tmp_path / 'finsight'
        root.mkdir()
        (root / '__init__.py').write_text('')

        assert find_folders_missing_readme(root) == ['.']

    def test_accepts_root_with_readme(self, tmp_path: Path) -> None:
        root = tmp_path / 'finsight'
        root.mkdir()
        (root / '__init__.py').write_text('')
        (root / 'README.md').write_text('# Root\n')

        assert find_folders_missing_readme(root) == []

    def test_flags_missing_child_readme(self, tmp_path: Path) -> None:
        root = tmp_path / 'finsight'
        child = root / 'child'
        child.mkdir(parents=True)
        (root / '__init__.py').write_text('')
        (root / 'README.md').write_text('# Root\n')
        (child / '__init__.py').write_text('')

        assert find_folders_missing_readme(root) == ['child']
