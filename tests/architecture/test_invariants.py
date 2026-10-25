# Architecture Invariant Tests
# These tests enforce invariants that static tools cannot express.
# Run with: pytest tests/architecture -v --tb=short -m architecture

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# ============================================================
# Helpers
# ============================================================

SRC_ROOT = Path(__file__).parent.parent.parent / 'src' / 'finsight'

# Modules that should NOT read environment variables directly
NO_ENV_MODULES = [
    'domain',
    'application',
    'adapters',
    'entrypoints',
    'composition',
]

# Vendor modules that should NOT be imported in domain/application
FORBIDDEN_VENDORS = {
    'boto3',
    'litellm',
    'langchain',
    'langgraph',
    'fastapi',
    'httpx',
    'openai',
    'anthropic',
    'pandas',
    'sqlalchemy',
    'psycopg',
    'asyncpg',
    'redis',
    'aiobotocore',
    'cohere',
    'pdfplumber',
    'pytesseract',
    'docx',
    'openpyxl',
    'tenacity',
    'structlog',
    'opentelemetry',
    'pydantic',
    'email_validator',
    'python_multipart',
}

# Patterns that indicate vendor branching in business code
VENDOR_BRANCHING_PATTERNS = [
    'textract',
    'tesseract',
    'pdfplumber',
    'litellm',
    'bedrock',
    'openai',
    'anthropic',
    'cohere',
]

# Functions/classes that should only be instantiated in composition/adapters
FORBIDDEN_CONSTRUCTORS = {
    'boto3.client',
    'boto3.resource',
    'httpx.Client',
    'httpx.AsyncClient',
    'litellm',
    'LiteLLM',
    'OpenAI',
    'Anthropic',
    'CohereClient',
    'AsyncCohereClient',
}

# Maximum lines per file/function (warn level)
MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 30


def get_python_files(package: str) -> list[Path]:
    """Get all Python files in a package."""
    package_path = SRC_ROOT / package
    if not package_path.exists():
        return []
    return list(package_path.rglob('*.py'))


def parse_python_file(filepath: Path) -> ast.Module:
    """Parse a Python file into an AST."""
    content = filepath.read_text()
    return ast.parse(content, filename=str(filepath))


def get_all_imports(tree: ast.Module) -> set[str]:
    """Extract all import names from an AST."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
    return imports


def get_all_calls(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract all function calls with line numbers."""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append((node.func.id, node.lineno))
            elif isinstance(node.func, ast.Attribute):
                calls.append((node.func.attr, node.lineno))
    return calls


def find_class_defs(tree: ast.Module) -> list[tuple[str, int, int]]:
    """Find all class definitions with start/end lines."""
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            end_line = node.end_lineno or node.lineno
            classes.append((node.name, node.lineno, end_line))
    return classes


def find_function_defs(tree: ast.Module) -> list[tuple[str, int, int]]:
    """Find all function definitions with start/end lines."""
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = node.end_lineno or node.lineno
            functions.append((node.name, node.lineno, end_line))
    return functions


# ============================================================
# Test: Only core/config reads env vars
# ============================================================


@pytest.mark.architecture
class TestNoEnvVarsOutsideConfig:
    """Ensure only core/config reads environment variables."""

    @pytest.mark.parametrize('module', NO_ENV_MODULES)
    def test_no_os_getenv(self, module: str) -> None:
        """No os.getenv calls outside core/config."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'os'
                    and node.func.attr == 'getenv'
                ):
                    pytest.fail(
                        f'{filepath}:{node.lineno}: '
                        f'Direct os.getenv() call found. '
                        f'Use core.config.get_config() instead.'
                    )

    @pytest.mark.parametrize('module', NO_ENV_MODULES)
    def test_no_os_environ(self, module: str) -> None:
        """No os.environ access outside core/config."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == 'os'
                    and node.attr == 'environ'
                ):
                    pytest.fail(
                        f'{filepath}:{node.lineno}: '
                        f'Direct os.environ access found. '
                        f'Use core.config.get_config() instead.'
                    )


# ============================================================
# Test: No vendor imports in domain/application
# ============================================================


@pytest.mark.architecture
class TestNoVendorImportsInBusinessCode:
    """Ensure domain and application don't import vendor libraries."""

    @pytest.mark.parametrize('module', ['domain', 'application'])
    def test_no_forbidden_imports(self, module: str) -> None:
        """No forbidden vendor imports in domain/application."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)
            imports = get_all_imports(tree)
            forbidden_found = imports & FORBIDDEN_VENDORS
            assert not forbidden_found, (
                f'{filepath}: Forbidden vendor imports found: {forbidden_found}. '
                f'Move vendor code to adapters/.'
            )

    @pytest.mark.parametrize('module', ['domain', 'application'])
    def test_no_vendor_branching(self, module: str) -> None:
        """No vendor-name string comparisons in business logic."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                compared = [node.left, *node.comparators]
                literals = [
                    item.value.lower()
                    for item in compared
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
                for literal in literals:
                    for pattern in VENDOR_BRANCHING_PATTERNS:
                        if pattern in literal:
                            pytest.fail(
                                f'{filepath}:{node.lineno}: Vendor name {pattern!r} is '
                                f'compared in business code. Choose behaviour via a port.'
                            )


# ============================================================
# Test: Every repo/search/cache method takes company_id
# ============================================================


@pytest.mark.architecture
class TestCompanyIdOnAllQueries:
    """Ensure all repository, search, and cache methods require company_id."""

    def _find_methods_without_company_id(self, package: str) -> list[tuple[str, str, int]]:
        """Find methods that don't have company_id parameter."""
        violations = []
        for filepath in get_python_files(package):
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods, properties, and __init__
                    if node.name.startswith('_'):
                        continue
                    if any(
                        isinstance(d, ast.Decorator)
                        for d in node.decorator_list
                        if isinstance(d.func, ast.Name) and d.func.id == 'property'
                    ):
                        continue

                    # Check parameters
                    args = node.args
                    param_names = [arg.arg for arg in args.args]
                    param_names += [arg.arg for arg in args.kwonlyargs]
                    if args.vararg:
                        param_names.append(args.vararg.arg)
                    if args.kwarg:
                        param_names.append(args.kwarg.arg)

                    # Check if this looks like a data access method
                    method_name = node.name.lower()
                    is_data_method = any(
                        keyword in method_name
                        for keyword in [
                            'get',
                            'find',
                            'search',
                            'query',
                            'fetch',
                            'load',
                            'list',
                            'retrieve',
                            'read',
                            'save',
                            'write',
                            'create',
                            'update',
                            'delete',
                            'upsert',
                            'insert',
                            'execute',
                        ]
                    )

                    if is_data_method and 'company_id' not in param_names:
                        violations.append((str(filepath), node.name, node.lineno))

        return violations

    def test_repositories_require_company_id(self) -> None:
        """All repository methods must take company_id."""
        violations = self._find_methods_without_company_id('adapters/repositories')
        assert not violations, 'Repository methods missing company_id parameter:\n' + '\n'.join(
            f'  {f}:{line} {m}' for f, m, line in violations
        )

    def test_vector_store_requires_company_id(self) -> None:
        """All vector store methods must take company_id."""
        violations = self._find_methods_without_company_id('adapters/vector_store')
        assert not violations, 'Vector store methods missing company_id parameter:\n' + '\n'.join(
            f'  {f}:{line} {m}' for f, m, line in violations
        )

    def test_cache_requires_company_id(self) -> None:
        """All cache methods must take company_id."""
        violations = self._find_methods_without_company_id('adapters/cache')
        assert not violations, 'Cache methods missing company_id parameter:\n' + '\n'.join(
            f'  {f}:{line} {m}' for f, m, line in violations
        )


# ============================================================
# Test: Money uses Decimal, never float
# ============================================================


@pytest.mark.architecture
class TestMoneyUsesDecimal:
    """Ensure Money value object uses Decimal, not float."""

    def test_money_amount_is_decimal(self) -> None:
        """Money.amount must be annotated as Decimal."""
        money_files = list((SRC_ROOT / 'domain' / 'value_objects').glob('*money*.py'))
        if not money_files:
            pytest.skip('Money value object not yet implemented')

        for filepath in money_files:
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and 'money' in node.name.lower():
                    for item in node.body:
                        if (
                            isinstance(item, ast.AnnAssign)
                            and isinstance(item.target, ast.Name)
                            and item.target.id == 'amount'
                        ):
                            # Check annotation
                            if isinstance(item.annotation, ast.Name):
                                assert item.annotation.id == 'Decimal', (
                                    f'{filepath}:{item.lineno}: Money.amount must be Decimal, '
                                    f'got {item.annotation.id}'
                                )
                            elif isinstance(item.annotation, ast.Subscript):
                                assert isinstance(item.annotation.value, ast.Name), (
                                    f'{filepath}:{item.lineno}: Money.amount annotation unclear'
                                )
                                assert item.annotation.value.id == 'Decimal', (
                                    f'{filepath}:{item.lineno}: Money.amount must be Decimal'
                                )

    def test_no_float_in_value_objects(self) -> None:
        """No float type annotations in value_objects package."""
        for filepath in get_python_files('domain/value_objects'):
            tree = parse_python_file(filepath)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.annotation, ast.Name)
                    and node.annotation.id == 'float'
                ):
                    pytest.fail(
                        f'{filepath}:{node.lineno}: float annotation found in value_objects. '
                        f'Use Decimal for monetary values.'
                    )


# ============================================================
# Test: No hidden dependency construction
# ============================================================


@pytest.mark.architecture
class TestNoHiddenDependencyConstruction:
    """Ensure adapters/composition are the only places constructing external clients."""

    @pytest.mark.parametrize('module', ['domain', 'application', 'entrypoints'])
    def test_no_direct_client_construction(self, module: str) -> None:
        """No direct boto3/httpx/litellm client construction in business code."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)
            calls = get_all_calls(tree)
            for func_name, lineno in calls:
                if func_name in FORBIDDEN_CONSTRUCTORS:
                    pytest.fail(
                        f'{filepath}:{lineno}: Direct construction of {func_name} found. '
                        f'Use dependency injection via composition root.'
                    )


# ============================================================
# Test: One main class per file, file matches class name
# ============================================================


@pytest.mark.architecture
class TestFileClassNaming:
    """Ensure one main class per file, filename matches class name."""

    def test_file_class_naming(self) -> None:
        """Each .py file should have a main class matching the filename."""
        # Files allowed to have multiple classes
        allowed_multi_class = {
            'models.py',  # Config models
            'errors.py',  # Error classes
            'types.py',  # Type definitions
        }

        # Files where class name doesn't match filename (legacy/existing)
        allowed_name_mismatch = {
            'loader.py': 'ConfigLoader',
        }

        for filepath in SRC_ROOT.rglob('*.py'):
            # Skip __init__.py, test files, and config files
            if filepath.name in {'__init__.py', 'conftest.py'}:
                continue
            if 'test' in filepath.parts:
                continue

            tree = parse_python_file(filepath)
            classes = find_class_defs(tree)

            # Filter out private classes, exceptions, and base classes
            public_classes = [
                (name, start, end)
                for name, start, end in classes
                if not name.startswith('_')
                and not name.endswith('Error')
                and not name.endswith('Exception')
                and name not in {'Config', 'Settings', 'BaseModel', 'Protocol'}
            ]

            if not public_classes:
                continue  # No public classes - might be a module with only functions

            # Allow multiple classes in certain files
            if filepath.name in allowed_multi_class:
                continue

            # Allow name mismatch for certain files
            if filepath.name in allowed_name_mismatch:
                expected_class = allowed_name_mismatch[filepath.name]
                if len(public_classes) == 1 and public_classes[0][0] == expected_class:
                    continue

            if len(public_classes) > 1:
                pytest.fail(
                    f'{filepath}: Multiple public classes found: '
                    f'{[c[0] for c in public_classes]}. '
                    f'One main class per file.'
                )

            class_name = public_classes[0][0]
            expected_filename = self._to_snake_case(class_name) + '.py'
            if filepath.name != expected_filename:
                pytest.fail(
                    f'{filepath}: Filename should be {expected_filename} '
                    f'to match class {class_name}'
                )

    def _to_snake_case(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# ============================================================
# Test: Every folder has a README.md
# ============================================================


@pytest.mark.architecture
class TestFolderReadmes:
    """Ensure every package folder has a README.md."""

    def test_all_folders_have_readme(self) -> None:
        """Every directory under src/finsight should have README.md."""
        missing = []
        for dirpath in SRC_ROOT.rglob('*'):
            if dirpath.is_dir() and not dirpath.name.startswith('.'):
                # Skip __pycache__ and similar
                if dirpath.name == '__pycache__':
                    continue
                readme = dirpath / 'README.md'
                if not readme.exists():
                    # Check if it's a leaf package (has .py files) or has subpackages
                    has_py = any(dirpath.glob('*.py'))
                    has_subdirs = any(
                        d.is_dir() for d in dirpath.iterdir() if not d.name.startswith('.')
                    )
                    if has_py or has_subdirs:
                        missing.append(str(dirpath.relative_to(SRC_ROOT)))

        assert not missing, 'Missing README.md in folders:\n' + '\n'.join(
            f'  src/finsight/{m}' for m in missing
        )


# ============================================================
# Test: File and function size limits (warning only for now)
# ============================================================


@pytest.mark.architecture
class TestSizeLimits:
    """Warn on oversized files/functions."""

    def test_file_line_count(self) -> None:
        """Files should be under ~300 lines."""
        oversized = []
        for filepath in SRC_ROOT.rglob('*.py'):
            if '__pycache__' in filepath.parts:
                continue
            lines = filepath.read_text().count('\n')
            if lines > MAX_FILE_LINES:
                oversized.append((str(filepath.relative_to(SRC_ROOT)), lines))

        if oversized:
            # Warn for now - can be upgraded to error later
            print('\n⚠️  Files exceeding 300 lines:')
            for path, lines in oversized:
                print(f'  {path}: {lines} lines')

    def test_function_line_count(self) -> None:
        """Functions should be under ~30 lines."""
        oversized = []
        for filepath in SRC_ROOT.rglob('*.py'):
            if '__pycache__' in filepath.parts:
                continue
            tree = parse_python_file(filepath)
            for name, start, end in find_function_defs(tree):
                if not name.startswith('_'):
                    lines = end - start + 1
                    if lines > MAX_FUNCTION_LINES:
                        oversized.append((str(filepath.relative_to(SRC_ROOT)), name, lines))

        if oversized:
            print('\n⚠️  Functions exceeding 30 lines:')
            for path, name, lines in oversized[:20]:  # Limit output
                print(f'  {path}::{name}: {lines} lines')


# ============================================================
# Test: No 'if env == "prod"' in business code
# ============================================================


@pytest.mark.architecture
class TestNoEnvironmentChecksInBusinessCode:
    """Ensure no environment-specific logic in domain/application/adapters."""

    @pytest.mark.parametrize('module', ['domain', 'application', 'adapters', 'entrypoints'])
    def test_no_prod_checks(self, module: str) -> None:
        """No Environment.PRODUCTION or 'production' string checks in business code."""
        for filepath in get_python_files(module):
            tree = parse_python_file(filepath)

            # Check for direct 'production' comparisons.
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                compared = [node.left, *node.comparators]
                literals = [
                    item.value.lower()
                    for item in compared
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
                if any('production' in literal for literal in literals):
                    pytest.fail(
                        f'{filepath}:{node.lineno}: '
                        f'Direct production/string environment check found. '
                        f'Use config switches instead.'
                    )

            # Check for Environment.PRODUCTION enum usage.
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and (
                    isinstance(node.value, ast.Name)
                    and node.value.id == 'Environment'
                    and node.attr == 'PRODUCTION'
                ):
                    pytest.fail(
                        f'{filepath}:{node.lineno}: '
                        f'Direct Environment.PRODUCTION check found. '
                        f'Use config switches instead.'
                    )
