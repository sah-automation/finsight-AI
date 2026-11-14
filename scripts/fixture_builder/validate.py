"""Validate the generated golden question set.

The generator can produce a syntactically valid file that is still wrong: a
duplicate id, a citation to a page that does not exist, an expected amount that
does not match the answer text, or a set too thin to score 95% on. This module
checks all of that before anything is committed.

Validation reads the documents that were just built, so a citation is checked
against the real page count and the section labels the writers recorded. For
PDFs with a text layer the label must also appear in that page's extracted text,
which catches a heading that drifted onto the neighbouring page.

Run through ``uv run python scripts/fixture_builder``; never edit the outputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pdfplumber
import yaml

from fixture_builder.questions import OUTPUT_DIR

if TYPE_CHECKING:
    from pathlib import Path

    from fixture_builder.documents import GeneratedDocument

ROLES = (
    'executive_leadership',
    'corporate_finance_planners',
    'audit_compliance',
    'system_admin',
)

COMPANIES = ('company-a', 'company-b', 'both')

CATEGORIES = (
    'financials',
    'metrics',
    'forecasts',
    'risks',
    'decisions',
    'documents',
    'audit',
)

DIFFICULTIES = ('easy', 'medium', 'hard')

UNITS = ('million', 'billion', '1', 'percent', 'count', 'ratio')

# Group file name -> id prefix. Keeps ids and files in step.
GROUP_PREFIXES = {
    'revenue': 'rev',
    'margins': 'mar',
    'balance_sheet': 'bal',
    'cash_flow': 'cfl',
    'budget_vs_actual': 'bud',
    'ledger': 'led',
    'bank_statement': 'bnk',
    'invoice': 'inv',
    'board_notes': 'brd',
    'company_b': 'cmb',
    'comparisons': 'cmp',
    'citations': 'cit',
    'insufficient_data': 'ins',
    'access': 'acc',
    'messy_phrasing': 'msy',
    'versioning': 'ver',
}

# Minimum size of the set. The release gate is a 95% numeric-accuracy rate over
# this set, so it has to be big and varied enough to mean something.
MIN_TOTAL = 100
MIN_NUMERIC = 20
MIN_INSUFFICIENT = 10
MIN_READERS = ('pdf', 'scan', 'image', 'xlsx', 'csv', 'docx')

# The release gate, mirrored in thresholds.yaml.
NUMERIC_ACCURACY_GATE = 0.95
CITATION_ACCURACY_GATE = 1.0

ID_PATTERN = re.compile(r'^[a-z]{3}-\d{3}$')
NUMBER_PATTERN = re.compile(r'^-?\d+(?:\.\d+)?$')


@dataclass
class Report:
    """Collected facts about the set, printed by the CLI."""

    total: int = 0
    numeric: int = 0
    insufficient: int = 0
    denied: int = 0
    roles: set[str] = field(default_factory=set)
    companies: set[str] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)
    readers: set[str] = field(default_factory=set)
    per_group: dict[str, int] = field(default_factory=dict)


class ValidationError(Exception):
    """One or more questions failed validation."""


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _normalise(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def _page_text(doc: GeneratedDocument) -> dict[int, str]:
    """Extract per-page text for born-digital PDFs so labels can be checked.

    Returns an empty mapping for files that have no text layer (scan, image) or
    are not PDFs at all; those fall back to the recorded section map.
    """
    if doc.meta.file_type not in ('pdf', 'scan'):
        return {}
    with pdfplumber.open(str(doc.path)) as pdf:
        return {
            index + 1: _normalise(page.extract_text() or '') for index, page in enumerate(pdf.pages)
        }


def _number_forms(value: float, decimals: int) -> list[str]:
    """Renderings that count as the same expected number in prose."""
    forms: set[str] = set()
    for number in (value, abs(value)):
        for size in {decimals, 0, 1, 2}:
            rendered = f'{number:,.{size}f}'
            forms.add(rendered)
            forms.add(rendered.replace(',', ''))
    return sorted(forms, key=len, reverse=True)


def _check_number(
    answer: str | None, number: dict[str, Any], where: str, errors: list[str]
) -> None:
    value_text = str(number.get('value', ''))
    if not NUMBER_PATTERN.match(value_text):
        _fail(errors, f'{where}: value {value_text!r} is not a plain number')
        return
    unit = number.get('unit')
    if unit not in UNITS:
        _fail(errors, f'{where}: unit {unit!r} is not one of {UNITS}')
        return
    currency = number.get('currency')
    if unit in ('percent', 'count', 'ratio') and currency is not None:
        _fail(errors, f'{where}: unit {unit} must have a null currency, got {currency!r}')
    if unit in ('million', 'billion', '1') and currency != 'USD':
        _fail(errors, f'{where}: unit {unit} must have currency USD, got {currency!r}')
    if answer is None:
        _fail(errors, f'{where}: has an expected number but no answer text')
        return

    value = float(value_text)
    decimals = len(value_text.split('.')[1]) if '.' in value_text else 0
    forms = _number_forms(value, decimals)
    normalised = _normalise(answer)
    if not any(_normalise(form) in normalised for form in forms):
        _fail(
            errors,
            f'{where}: answer does not contain expected value {value_text} '
            f'(tried {", ".join(forms[:4])})',
        )


def _check_citation(
    citation: dict[str, Any],
    where: str,
    documents: dict[str, GeneratedDocument],
    texts: dict[str, dict[int, str]],
    errors: list[str],
) -> str | None:
    name = citation.get('document')
    if name not in documents:
        _fail(errors, f'{where}: cites unknown document {name!r}')
        return None
    doc = documents[name]
    page = citation.get('page')
    if not isinstance(page, int) or page < 1:
        _fail(errors, f'{where}: page {page!r} is not a positive integer')
        return doc.meta.file_type
    if page > doc.meta.pages:
        _fail(errors, f'{where}: cites page {page} but {name} has {doc.meta.pages} pages')
        return doc.meta.file_type

    table = citation.get('table')
    if table is not None:
        recorded = doc.sections.get(page, ())
        if table not in recorded:
            _fail(
                errors,
                f'{where}: table {table!r} is not recorded on page {page} of {name} '
                f'(recorded: {", ".join(recorded) or "none"})',
            )
        elif doc.meta.file_type == 'pdf':
            text = texts.get(name, {}).get(page, '')
            if text and _normalise(table) not in text:
                _fail(
                    errors,
                    f'{where}: table {table!r} is recorded on page {page} of {name} '
                    'but does not appear in the extracted page text',
                )
    return doc.meta.file_type


def _check_identity(
    question: dict[str, Any],
    *,
    group: str,
    expected_prefix: str,
    seen_ids: dict[str, str],
    errors: list[str],
) -> str:
    """Check the id is well formed and unique. Return the error label."""
    qid = str(question.get('id', ''))
    where = f'{group}/{qid or "<no id>"}'
    if not ID_PATTERN.match(qid):
        _fail(errors, f'{where}: id must look like abc-001')
    elif not qid.startswith(f'{expected_prefix}-'):
        _fail(errors, f'{where}: id prefix should be {expected_prefix!r} for group {group!r}')
    if qid in seen_ids:
        _fail(errors, f'{where}: duplicate id, already used in {seen_ids[qid]}')
    seen_ids[qid] = group
    if not str(question.get('question', '')).strip():
        _fail(errors, f'{where}: empty question text')
    return where


def _check_labels(question: dict[str, Any], where: str, report: Report, errors: list[str]) -> None:
    """Check the descriptive fields and record them for coverage."""
    category = question.get('category')
    if category not in CATEGORIES:
        _fail(errors, f'{where}: category {category!r} is not in permissions.yaml')
    else:
        report.categories.add(str(category))
    difficulty = question.get('difficulty')
    if difficulty not in DIFFICULTIES:
        _fail(errors, f'{where}: difficulty {difficulty!r} is not in {DIFFICULTIES}')
    role = question.get('role')
    if role not in ROLES:
        _fail(errors, f'{where}: role {role!r} is not one of {ROLES}')
    else:
        report.roles.add(str(role))
    company = question.get('company')
    if company not in COMPANIES:
        _fail(errors, f'{where}: company {company!r} is not one of {COMPANIES}')
    else:
        report.companies.add(str(company))
    tags = question.get('tags')
    if not isinstance(tags, list) or not tags:
        _fail(errors, f'{where}: needs at least one tag')


def _check_expected(
    question: dict[str, Any],
    where: str,
    *,
    report: Report,
    documents_by_name: dict[str, GeneratedDocument],
    texts: dict[str, dict[int, str]],
    errors: list[str],
) -> None:
    """Check the expected block: answer, numbers and citations."""
    expected = question.get('expected')
    if not isinstance(expected, dict):
        _fail(errors, f'{where}: missing expected block')
        return
    answer = expected.get('answer')
    numbers = expected.get('numbers') or []
    citations = expected.get('citations') or []
    insufficient = expected.get('insufficient_data')
    denied = expected.get('access_denied', False)

    if not isinstance(insufficient, bool):
        _fail(errors, f'{where}: insufficient_data must be true or false')
    if insufficient:
        report.insufficient += 1
        if answer is not None:
            _fail(errors, f'{where}: insufficient data must have a null answer')
        if numbers or citations:
            _fail(errors, f'{where}: insufficient data must not carry numbers or citations')
        if denied:
            _fail(errors, f'{where}: cannot be both insufficient data and access denied')
        return
    if denied:
        report.denied += 1
        if answer is not None or numbers or citations:
            _fail(
                errors,
                f'{where}: access denied must not carry an answer, numbers or citations',
            )
        return

    _check_answerable(
        where,
        answer=answer,
        numbers=numbers,
        citations=citations,
        report=report,
        documents_by_name=documents_by_name,
        texts=texts,
        errors=errors,
    )


def _check_answerable(
    where: str,
    *,
    answer: object,
    numbers: list[Any],
    citations: list[Any],
    report: Report,
    documents_by_name: dict[str, GeneratedDocument],
    texts: dict[str, dict[int, str]],
    errors: list[str],
) -> None:
    """Check a question that expects an answer: text, citations and numbers."""
    if not isinstance(answer, str) or not answer.strip():
        _fail(errors, f'{where}: answerable question needs answer text')
    if not citations:
        _fail(errors, f'{where}: answerable question needs at least one citation')
    for citation in citations:
        if not isinstance(citation, dict):
            _fail(errors, f'{where}: citation must be a mapping')
            continue
        reader = _check_citation(citation, where, documents_by_name, texts, errors)
        if reader:
            report.readers.add(reader)

    if numbers:
        report.numeric += 1
    for index, number in enumerate(numbers):
        if not isinstance(number, dict):
            _fail(errors, f'{where}: number {index} must be a mapping')
            continue
        text = answer if isinstance(answer, str) else None
        _check_number(text, number, f'{where}[{index}]', errors)


def _check_floors(report: Report, errors: list[str]) -> None:
    """Check the set is big enough to score 95% on."""
    if report.total < MIN_TOTAL:
        _fail(errors, f'only {report.total} questions, need at least {MIN_TOTAL}')
    if report.numeric < MIN_NUMERIC:
        _fail(errors, f'only {report.numeric} numeric questions, need at least {MIN_NUMERIC}')
    if report.insufficient < MIN_INSUFFICIENT:
        _fail(
            errors,
            f'only {report.insufficient} insufficient-data cases, need at least {MIN_INSUFFICIENT}',
        )
    if report.denied < 1:
        _fail(errors, 'need at least one access-denied case')


def _check_coverage(
    report: Report,
    documents_by_name: dict[str, GeneratedDocument],
    cited: set[str | None],
    questions_dir: Path,
    errors: list[str],
) -> None:
    """Check the set covers every role, reader and company, and the gate is recorded."""
    _check_floors(report, errors)
    missing_roles = set(ROLES) - report.roles
    if missing_roles:
        _fail(errors, f'no question for roles: {", ".join(sorted(missing_roles))}')
    missing_readers = set(MIN_READERS) - report.readers
    if missing_readers:
        _fail(errors, f'no question cites a document read by: {", ".join(sorted(missing_readers))}')
    missing_companies = set(COMPANIES) - report.companies
    if missing_companies:
        _fail(errors, f'no question for companies: {", ".join(sorted(missing_companies))}')

    uncited = set(documents_by_name) - cited
    if uncited:
        _fail(errors, f'documents never cited: {", ".join(sorted(uncited))}')

    readme = questions_dir / 'README.md'
    if readme.exists() and '95%' not in readme.read_text(encoding='utf-8'):
        _fail(errors, f'{readme} must state the 95% numeric-accuracy gate')

    threshold_file = questions_dir / 'thresholds.yaml'
    if not threshold_file.exists():
        _fail(errors, f'{threshold_file} is missing; the runner needs the release gate')
        return
    threshold = yaml.safe_load(threshold_file.read_text(encoding='utf-8')) or {}
    if threshold.get('numeric_accuracy') != NUMERIC_ACCURACY_GATE:
        _fail(errors, f'{threshold_file}: numeric_accuracy must be 0.95')
    if threshold.get('citation_accuracy') != CITATION_ACCURACY_GATE:
        _fail(errors, f'{threshold_file}: citation_accuracy must be 1.0')
    if threshold.get('minimum_questions', 0) < MIN_TOTAL:
        _fail(errors, f'{threshold_file}: minimum_questions is below the coverage floor')


def validate(
    groups: dict[str, list[dict[str, Any]]],
    documents: list[GeneratedDocument],
    questions_dir: Path = OUTPUT_DIR,
) -> Report:
    """Check every question and return a report, raising on the first batch of errors."""
    errors: list[str] = []
    report = Report()
    seen_ids: dict[str, str] = {}
    documents_by_name = {doc.meta.filename: doc for doc in documents}

    cited = {
        citation.get('document')
        for questions in groups.values()
        for question in questions
        for citation in question.get('expected', {}).get('citations') or []
        if isinstance(citation, dict)
    }
    texts = {
        str(name): _page_text(documents_by_name[str(name)])
        for name in sorted(cited)
        if name in documents_by_name
    }

    for group, questions in groups.items():
        expected_prefix = GROUP_PREFIXES.get(group)
        if expected_prefix is None:
            _fail(errors, f'{group}: unknown question group')
            continue
        report.per_group[group] = len(questions)
        report.total += len(questions)
        for question in questions:
            where = _check_identity(
                question,
                group=group,
                expected_prefix=expected_prefix,
                seen_ids=seen_ids,
                errors=errors,
            )
            _check_labels(question, where, report, errors)
            _check_expected(
                question,
                where,
                report=report,
                documents_by_name=documents_by_name,
                texts=texts,
                errors=errors,
            )

    _check_coverage(report, documents_by_name, cited, questions_dir, errors)

    if errors:
        raise ValidationError('\n'.join(errors))
    return report
