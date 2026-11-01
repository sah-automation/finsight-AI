# Architecture Invariant Tests
# These tests enforce invariants that static tools cannot express.
# Run with: pytest tests/architecture -v --tb=short -m architecture

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.support.ast_inspection import (
    find_class_defs,
    find_folders_missing_readme,
    find_forbidden_constructor_calls,
    find_function_defs,
    find_methods_without_company_id,
    get_all_imports,
    get_python_files,
    parse_python_file,
)

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
# are defined in tests/support/ast_inspection.py.

# Maximum lines per file/function
MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 30

# Reviewed exceptions for module size. Each entry must include a reason, an
# owner, and a removal condition. Adding an entry without these fields makes
# the size gate fail.
OVERSIZED_FILE_EXCEPTIONS: dict[str, dict[str, str]] = {
    'core/errors/__init__.py': {
        'reason': 'Central error class registry for Phase 1.',
        'owner': 'core platform',
        'removal_condition': 'Split into per-domain error modules when registry exceeds 450 lines.',
    },
    'adapters/readers/textract_reader.py': {
        'reason': 'Textract adapter bundles sync/async polling and response parsing.',
        'owner': 'adapters',
        'removal_condition': 'Extract polling and parsing helpers once contract tests guard behavior.',
    },
    'application/ask_question/ask_question.py': {
        'reason': 'Q&A orchestration retains legacy heavy execution path.',
        'owner': 'application',
        'removal_condition': 'Finish named-step extraction started in H11.',
    },
    'application/delete_document/delete_document.py': {
        'reason': 'Delete orchestration includes compatibility aliases.',
        'owner': 'application',
        'removal_condition': 'Remove aliases after H20 compatibility window.',
    },
    'application/ingest_document/pipeline_step_worker.py': {
        'reason': 'Ingestion worker keeps generic property proxy helpers.',
        'owner': 'application',
        'removal_condition': 'Replace __getattr__ fallbacks with explicit inputs.',
    },
    'application/ingest_document/scan_worker.py': {
        'reason': 'Scan worker keeps provider-specific payload helpers.',
        'owner': 'application',
        'removal_condition': 'Move payload helpers into readers adapters.',
    },
    'application/ingest_document/upload_document.py': {
        'reason': 'Upload orchestration keeps broad constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Narrow constructor resolution into typed dependencies.',
    },
    'application/onboarding/create_company.py': {
        'reason': 'Onboarding retains alias and normalization helpers.',
        'owner': 'application',
        'removal_condition': 'Collapse alias helpers after H20.',
    },
    'application/reprocess/reprocess.py': {
        'reason': 'Reprocess orchestration retains helper duplicates.',
        'owner': 'application',
        'removal_condition': 'Share helpers via the ingest application module.',
    },
    'application/source_viewer/source_viewer.py': {
        'reason': 'Source viewer combines reader decoding and authorization helpers.',
        'owner': 'application',
        'removal_condition': 'Split decoded lokator handling from viewer orchestration.',
    },
    'application/update_document/update_document.py': {
        'reason': 'Update orchestration retains compatibility aliases.',
        'owner': 'application',
        'removal_condition': 'Remove aliases after H20 compatibility window.',
    },
    'composition/composition_container.py': {
        'reason': 'Composition container preserves compatibility exports.',
        'owner': 'composition',
        'removal_condition': 'Collapse exports to canonical builders.',
    },
    'composition/container.py': {
        'reason': 'Composition root is the aggregate resolver and alias surface.',
        'owner': 'composition',
        'removal_condition': 'Move alias block behind explicit compatibility module.',
    },
    'composition/reader_registry.py': {
        'reason': 'Reader registry combines built-in and custom registration paths.',
        'owner': 'composition',
        'removal_condition': 'Extract custom registration strategy.',
    },
}

# Reviewed exceptions for oversized public functions whose signatures/contracts
# make the documented 30-line guidance impractical today.
OVERSIZED_FUNCTION_EXCEPTIONS: dict[str, dict[str, str]] = {
    'composition/reader_factory.py::create': {
        'reason': 'Factory constructor retains full diagnostic signature.',
        'owner': 'composition',
        'removal_condition': 'Split signature into a typed request object.',
    },
    'adapters/waiting_line/waiting_line_settings.py::from_kwargs': {
        'reason': 'Legacy kwargs adapter signature.',
        'owner': 'adapters',
        'removal_condition': 'Collapse to typed settings model.',
    },
    'domain/ports/audit_log.py::append': {
        'reason': 'Append port is the single aggregate audit entry contract.',
        'owner': 'domain',
        'removal_condition': 'Split into focused audit event types.',
    },
    'domain/entities/chunk.py::create': {
        'reason': 'Chunk factory keeps backward-compatible signature.',
        'owner': 'domain',
        'removal_condition': 'Introduce typed chunk construction input.',
    },
    'core/config/models/documents_config.py::validate_per_company_reader_overrides': {
        'reason': 'Pydantic validators require a single method.',
        'owner': 'core config',
        'removal_condition': 'Extract validation helpers behind a thin validator.',
    },
    'domain/ports/tracing_port.py::start_span': {
        'reason': 'Tracing port aggregate signature.',
        'owner': 'domain',
        'removal_condition': 'Split span configuration object.',
    },
    'domain/ports/metering_port.py::record_usage': {
        'reason': 'Metering port aggregate signature.',
        'owner': 'domain',
        'removal_condition': 'Split usage payload object.',
    },
    'adapters/tracing/disabled_tracer.py::start_span': {
        'reason': 'Disabled tracer mirrors port signature exactly.',
        'owner': 'adapters',
        'removal_condition': 'Split span configuration object in port.',
    },
}


# ============================================================
# Test: Only core/config reads env vars
# ============================================================


@pytest.mark.architecture
class TestNoEnvVarsOutsideConfig:
    """Ensure only core/config reads environment variables."""

    @pytest.mark.parametrize('module', NO_ENV_MODULES)
    def test_no_os_getenv(self, module: str) -> None:
        """No os.getenv calls outside core/config."""
        for filepath in get_python_files(SRC_ROOT / module):
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
        for filepath in get_python_files(SRC_ROOT / module):
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
        for filepath in get_python_files(SRC_ROOT / module):
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
        for filepath in get_python_files(SRC_ROOT / module):
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
        return find_methods_without_company_id(SRC_ROOT / package)

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
        """No float type annotations in value_objects package (except Confidence)."""
        allowed_float_files = {'confidence.py'}
        for filepath in get_python_files(SRC_ROOT / 'domain/value_objects'):
            if filepath.name in allowed_float_files:
                continue
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
        violations = find_forbidden_constructor_calls(SRC_ROOT / module)
        assert not violations, 'Direct external client construction found:\n' + '\n'.join(
            f'  {filepath}:{lineno} {name}' for filepath, name, lineno in violations
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
        """Every package folder, including src/finsight itself, has README.md."""
        missing = find_folders_missing_readme(SRC_ROOT)
        assert not missing, 'Missing README.md in folders:\n' + '\n'.join(
            f'  src/finsight/{m}' for m in missing
        )


# ============================================================
# Test: File and function size limits
# ============================================================


@pytest.mark.architecture
class TestSizeLimits:
    """Files under 300 lines and public functions under 30 lines."""

    def test_file_line_count(self) -> None:
        """Files should be under ~300 lines unless a reviewed exception applies."""
        oversized = []
        for filepath in SRC_ROOT.rglob('*.py'):
            if '__pycache__' in filepath.parts:
                continue
            lines = filepath.read_text().count('\n')
            if lines <= MAX_FILE_LINES:
                continue
            relative = str(filepath.relative_to(SRC_ROOT))
            exception = OVERSIZED_FILE_EXCEPTIONS.get(relative)
            if exception is None:
                oversized.append(f'{relative}: {lines} lines')
                continue
            for required in ('reason', 'owner', 'removal_condition'):
                if not exception.get(required):
                    oversized.append(f'{relative}: missing exception field {required}')

        assert not oversized, 'Oversized files without a valid exception:\n' + '\n'.join(
            f'  {item}' for item in oversized
        )

    def test_function_line_count(self) -> None:
        """Public functions should be under ~30 lines."""
        oversized = []
        for filepath in SRC_ROOT.rglob('*.py'):
            if '__pycache__' in filepath.parts:
                continue
            relative = str(filepath.relative_to(SRC_ROOT))
            tree = parse_python_file(filepath)
            for name, start, end in find_function_defs(tree):
                if name.startswith('_'):
                    continue
                lines = end - start + 1
                if lines <= MAX_FUNCTION_LINES:
                    continue
                key = f'{relative}::{name}'
                oversized.append(f'{key}: {lines} lines')

        # Function exceptions, kept separate so a new oversized function fails.
        for key in list(oversized):
            exception_name = key.split(': ', 1)[0]
            if exception_name in OVERSIZED_FUNCTION_EXCEPTIONS and all(
                OVERSIZED_FUNCTION_EXCEPTIONS[exception_name].get(field)
                for field in ('reason', 'owner', 'removal_condition')
            ):
                oversized.remove(key)

        assert not oversized, 'Oversized functions:\n' + '\n'.join(
            f'  {item}' for item in oversized
        )


# ============================================================
# Test: No 'if env == "prod"' in business code
# ============================================================


@pytest.mark.architecture
class TestNoEnvironmentChecksInBusinessCode:
    """Ensure no environment-specific logic in domain/application/adapters."""

    @pytest.mark.parametrize('module', ['domain', 'application', 'adapters', 'entrypoints'])
    def test_no_prod_checks(self, module: str) -> None:
        """No Environment.PRODUCTION or 'production' string checks in business code."""
        for filepath in get_python_files(SRC_ROOT / module):
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
