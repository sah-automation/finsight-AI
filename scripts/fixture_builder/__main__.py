"""Build the sample documents and the golden question set.

Usage::

    uv run python scripts/fixture_builder            # rebuild everything
    uv run python scripts/fixture_builder --check    # fail if outputs are stale

The same run writes the documents, the manifest, the questions and a thresholds
file, then validates the questions against the documents it just produced. A
failure exits non-zero, so it can be wired into CI.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# `python scripts/fixture_builder` puts the package directory on sys.path, not
# its parent, so absolute imports from the package need the parent added.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixture_builder import documents, questions, validate
from fixture_builder.model import build_company_a, build_company_b

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCUMENT_DIR = REPO_ROOT / 'tests/fixtures/documents'
DEFAULT_QUESTION_DIR = REPO_ROOT / 'tests/golden/questions'

# The pre-commit hook refuses files above 500 KB. Check before the hook does so
# the failure names the file and the reason.
MAX_FILE_BYTES = 500 * 1024

# Hand-written files that live in the generated folders. They are not produced by
# this tool, so the drift check must ignore them.
NON_GENERATED = frozenset({'README.md', '_template.yaml'})


def _check_sizes(docs: list[documents.GeneratedDocument], errors: list[str]) -> None:
    for doc in docs:
        size = doc.path.stat().st_size
        if size > MAX_FILE_BYTES:
            errors.append(
                f'{doc.meta.filename} is {size:,} bytes, over the 500 KB pre-commit limit'
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='fixture_builder',
        description='Build the anonymized sample documents and the golden question set.',
    )
    parser.add_argument('--document-dir', type=Path, default=DEFAULT_DOCUMENT_DIR)
    parser.add_argument('--question-dir', type=Path, default=DEFAULT_QUESTION_DIR)
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Ignore the one-day SEC facts cache and download fresh data.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Build into a temporary directory and report differences instead of writing.',
    )
    args = parser.parse_args(argv)

    document_dir: Path = args.document_dir
    question_dir: Path = args.question_dir

    if args.check:
        scratch = Path(tempfile.mkdtemp(prefix='fixture-check-'))
        document_dir = scratch / 'documents'
        question_dir = scratch / 'questions'
        # Validation reads the committed README for the 95% gate; every other
        # file in the scratch directory must come from this build.
        question_dir.mkdir(parents=True, exist_ok=True)
        readme = DEFAULT_QUESTION_DIR / 'README.md'
        if readme.exists():
            (question_dir / 'README.md').write_bytes(readme.read_bytes())

    model_a = build_company_a(refresh=args.refresh)
    model_b = build_company_b(refresh=args.refresh)

    docs = documents.build_all(model_a, model_b, document_dir)
    documents.write_manifest(docs, document_dir / 'manifest.yaml')
    _report_documents(docs)

    groups = questions.build_questions(model_a, model_b)
    questions.write_questions(groups, question_dir)
    questions.write_thresholds(question_dir)

    report = validate.validate(groups, docs, question_dir)
    _report_questions(report)

    errors: list[str] = []
    _check_sizes(docs, errors)
    if errors:
        _report_errors(errors)
        return 1

    if args.check:
        errors = _compare_outputs(
            document_dir, DEFAULT_DOCUMENT_DIR, question_dir, DEFAULT_QUESTION_DIR
        )
        if errors:
            _report_errors(
                [*errors, 'Outputs are stale. Run `uv run python scripts/fixture_builder`.']
            )
            return 1
        print('Outputs match the generator.')
        return 0

    print(f'Documents written to {document_dir}')
    print(f'Questions written to {question_dir}')
    return 0


def _report_documents(docs: list[documents.GeneratedDocument]) -> None:
    print('Documents')
    for doc in docs:
        size = doc.path.stat().st_size
        print(f'  {doc.meta.filename:58} {doc.meta.pages:>2}pp {size:>9,} B')


def _report_questions(report: validate.Report) -> None:
    print('Questions')
    for group, count in report.per_group.items():
        print(f'  {group:22} {count:>3}')
    print(
        f'  total {report.total}, numeric {report.numeric}, '
        f'insufficient {report.insufficient}, denied {report.denied}'
    )
    print(f'  roles {", ".join(sorted(report.roles))}')
    print(f'  readers {", ".join(sorted(report.readers))}')


def _report_errors(errors: list[str]) -> None:
    print(f'{len(errors)} problem(s):', file=sys.stderr)
    for error in errors:
        print(f'  - {error}', file=sys.stderr)


def _compare_outputs(
    built_documents: Path,
    committed_documents: Path,
    built_questions: Path,
    committed_questions: Path,
) -> list[str]:
    errors: list[str] = []
    for built_dir, committed_dir in (
        (built_documents, committed_documents),
        (built_questions, committed_questions),
    ):
        built = {path.name for path in built_dir.iterdir() if path.is_file()} - NON_GENERATED
        committed = (
            {path.name for path in committed_dir.iterdir() if path.is_file()}
            if committed_dir.exists()
            else set()
        ) - NON_GENERATED
        for name in sorted(built - committed):
            errors.append(f'{name} is generated but not committed')
        for name in sorted(committed - built):
            errors.append(f'{name} is committed but no longer generated')
        for name in sorted(built & committed):
            if (built_dir / name).read_bytes() != (committed_dir / name).read_bytes():
                errors.append(f'{name} differs from the committed copy')
    return errors


if __name__ == '__main__':
    sys.exit(main())
