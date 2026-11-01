"""Architecture invariant: no bare ``**kwargs`` constructors in application layer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.support.ast_inspection import get_python_files, parse_python_file

SRC_ROOT = Path(__file__).resolve().parents[2] / 'src' / 'finsight'
APPLICATION_ROOT = SRC_ROOT / 'application'

_ALLOWED_BARE_KWARGS_CONSTRUCTORS: dict[str, str] = {
    'DeleteDocument': 'application/delete_document/delete_document.py',
    'UpdateDocument': 'application/update_document/update_document.py',
    'UploadDocument': 'application/ingest_document/upload_document.py',
    'Reprocess': 'application/reprocess/reprocess.py',
    'SourceViewer': 'application/source_viewer/source_viewer.py',
    'CreateCompany': 'application/onboarding/create_company.py',
    'PipelineStepWorker': 'application/ingest_document/pipeline_step_worker.py',
    'ScanWorker': 'application/ingest_document/scan_worker.py',
    'UploadInput': 'application/ingest_document/models.py',
    'CreateCompanyInput': 'application/onboarding/models.py',
}

_BARE_KWARGS_METADATA: dict[str, dict[str, str]] = {
    'DeleteDocument': {
        'reason': 'Delete flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the delete flow is converted.',
    },
    'UpdateDocument': {
        'reason': 'Edit flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the edit flow is converted.',
    },
    'UploadDocument': {
        'reason': 'Upload flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the upload flow is converted.',
    },
    'Reprocess': {
        'reason': 'Reprocess flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the reprocess flow is converted.',
    },
    'SourceViewer': {
        'reason': 'Source viewer retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the source viewer flow is converted.',
    },
    'CreateCompany': {
        'reason': 'Onboarding create-company flow retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with typed constructor when the onboarding flow is converted.',
    },
    'PipelineStepWorker': {
        'reason': 'Pipeline step worker retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with explicit typed inputs when the worker is converted.',
    },
    'ScanWorker': {
        'reason': 'Scan worker retains alias-probing constructor resolution.',
        'owner': 'application',
        'removal_condition': 'Replace with explicit typed inputs when the worker is converted.',
    },
    'UploadInput': {
        'reason': 'Upload input DTO retains alias-friendly construction.',
        'owner': 'application',
        'removal_condition': 'Replace with typed construction when the upload flow is converted.',
    },
    'CreateCompanyInput': {
        'reason': 'Onboarding input DTO retains alias-friendly construction.',
        'owner': 'application',
        'removal_condition': 'Replace with typed construction when the onboarding flow is converted.',
    },
}

BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS: dict[str, dict[str, str]] = {}
for _class_name, _relative in _ALLOWED_BARE_KWARGS_CONSTRUCTORS.items():
    _metadata = _BARE_KWARGS_METADATA[_class_name]
    for _key in (_class_name, _relative, f'{_relative}::{_class_name}'):
        BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS[_key] = _metadata

CONSTRUCTOR_INVARIANT_EXCEPTIONS = BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS
BARE_KWARGS_EXCEPTIONS = BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS


def _bare_kwargs_constructors(application_root: Path) -> list[tuple[str, str, int]]:
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


def _matches_exception(relative: str, class_name: str) -> list[str]:
    candidates = (class_name, relative, f'{relative}::{class_name}')
    return [key for key in candidates if key in BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS]


@pytest.mark.architecture
class TestNoBareKwargsConstructors:
    def test_no_unexcepted_bare_kwargs_constructors(self) -> None:
        unapproved: list[str] = []
        invalid: list[str] = []
        for relative, class_name, lineno in _bare_kwargs_constructors(APPLICATION_ROOT):
            matched = _matches_exception(relative, class_name)
            if not matched:
                unapproved.append(f'{relative}:{lineno}: {class_name}')
                continue
            for key in matched:
                entry = BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS[key]
                for required in ('reason', 'owner', 'removal_condition'):
                    if not entry.get(required):
                        invalid.append(f'{key}: missing exception field {required}')

        messages: list[str] = []
        if unapproved:
            messages.append(
                'Bare **kwargs constructors without a valid exception:\n'
                + '\n'.join(f'  {item}' for item in unapproved)
            )
        if invalid:
            messages.append(
                'Bare **kwargs constructor exceptions missing required fields:\n'
                + '\n'.join(f'  {item}' for item in invalid)
            )
        assert not messages, '\n'.join(messages)


class TestConstructorInvariant(TestNoBareKwargsConstructors):
    pass


class TestBareKwargsConstructorInvariant(TestNoBareKwargsConstructors):
    pass
