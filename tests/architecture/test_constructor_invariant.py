"""Architecture invariant: no bare ``**kwargs`` constructors in application layer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.support.ast_inspection import get_python_files, parse_python_file

SRC_ROOT = Path(__file__).resolve().parents[2] / 'src' / 'finsight'
APPLICATION_ROOT = SRC_ROOT / 'application'

# Reviewed exceptions for application classes that still use a bare variadic
# keyword constructor. Keys are ``relative/path.py::ClassName`` so an exception
# is tied to the exact source location it was reviewed for. Each entry must
# include a reason, an owner, and a removal condition. The ask flow
# (AskQuestion) is intentionally absent: it now has a fully typed constructor.
# The edit (UpdateDocument) and delete (DeleteDocument) flows are seeded here and
# will drop when they are converted.
BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS: dict[str, dict[str, str]] = {
    'application/delete_document/delete_document.py::DeleteDocument': {
        'reason': 'Delete flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the delete flow is converted.',
    },
    'application/update_document/update_document.py::UpdateDocument': {
        'reason': 'Edit flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the edit flow is converted.',
    },
    'application/ingest_document/upload_document.py::UploadDocument': {
        'reason': 'Upload flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the upload flow is converted.',
    },
    'application/reprocess/reprocess.py::Reprocess': {
        'reason': 'Reprocess flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the reprocess flow is converted.',
    },
    'application/source_viewer/source_viewer.py::SourceViewer': {
        'reason': 'Source viewer retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the source viewer flow is converted.',
    },
    'application/onboarding/create_company.py::CreateCompany': {
        'reason': 'Onboarding create-company flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the onboarding flow is converted.',
    },
    'application/ingest_document/pipeline_step_worker.py::PipelineStepWorker': {
        'reason': 'Pipeline step worker retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with explicit typed inputs when the worker is converted.',
    },
    'application/ingest_document/scan_worker.py::ScanWorker': {
        'reason': 'Scan worker retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with explicit typed inputs when the worker is converted.',
    },
    'application/ingest_document/models.py::UploadInput': {
        'reason': 'Upload input DTO retains alias-friendly construction.',
        'owner': 'application',
        'removal_condition': 'Replace with typed construction when the upload flow is converted.',
    },
    'application/onboarding/models.py::CreateCompanyInput': {
        'reason': 'Onboarding input DTO retains alias-friendly construction.',
        'owner': 'application',
        'removal_condition': 'Replace with typed construction when the onboarding flow is converted.',
    },
}

# Alias names some callers may expect.
CONSTRUCTOR_INVARIANT_EXCEPTIONS = BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS
BARE_KWARGS_EXCEPTIONS = BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS


def _bare_kwargs_constructors(application_root: Path) -> list[tuple[str, str, int]]:
    """Return (relative_path, class_name, line) for bare ``**kwargs``/``**kw`` inits."""
    violations: list[tuple[str, str, int]] = []
    for filepath in get_python_files(application_root):
        tree = parse_python_file(filepath)
        relative = str(filepath.relative_to(SRC_ROOT))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != '__init__':
                    continue
                if item.args.kwarg is None:
                    continue
                if item.args.kwarg.arg not in ('kwargs', 'kw'):
                    continue
                violations.append((relative, node.name, item.lineno))
    return violations


@pytest.mark.architecture
class TestConstructorInvariant:
    """Fail when a new bare ``**kwargs`` constructor appears in application code."""

    def test_ask_flow_not_in_exception_list(self) -> None:
        """The converted ask flow must not have a constructor exception."""
        assert (
            'application/ask_question/ask_question.py::AskQuestion'
            not in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS
        )
        assert not any('AskQuestion' in key for key in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS)

    def test_edit_and_delete_flows_in_exception_list(self) -> None:
        """The unconverted edit and delete flows must be seeded as exceptions."""
        assert (
            'application/update_document/update_document.py::UpdateDocument'
            in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS
        )
        assert (
            'application/delete_document/delete_document.py::DeleteDocument'
            in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS
        )

    def test_exceptions_have_required_fields(self) -> None:
        """Every exception entry must be a reviewed exception."""
        for key, entry in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS.items():
            for required in ('reason', 'owner', 'removal_condition'):
                assert entry.get(required), f'{key}: missing exception field {required}'

    def test_no_unexpected_bare_kwargs_constructors(self) -> None:
        """All bare kwargs constructors must be reviewed exceptions."""
        unapproved: list[str] = []
        for relative, class_name, lineno in _bare_kwargs_constructors(APPLICATION_ROOT):
            key = f'{relative}::{class_name}'
            if key not in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS:
                unapproved.append(f'{relative}:{lineno}: {class_name}')

        assert not unapproved, (
            'Bare **kwargs constructors without a valid exception:\n'
            + '\n'.join(f'  {item}' for item in unapproved)
        )
