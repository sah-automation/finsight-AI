"""Scoring and comparison helpers for the golden set."""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import (
    Sequence,  # noqa: TC003
)
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
QUESTIONS_DIR = HERE / 'questions'
BASELINES_DIR = HERE / 'baselines'

PROFILE_BASELINE_FILES = {
    'pilot': BASELINES_DIR / 'pilot.json',
    'standard': BASELINES_DIR / 'standard.json',
}


@dataclass
class QuestionScore:
    question_id: str
    passed: bool
    numeric_ok: bool
    citation_ok: bool
    insufficient_ok: bool
    access_ok: bool
    reasons: tuple[str, ...] = ()
    numeric_accuracy: float = 0.0
    citation_accuracy: float = 0.0


def _as_text(value: object) -> str:
    return '' if value is None else str(value).strip()


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _citation_fields(citation: object) -> tuple[str, int | None, str | None]:
    if isinstance(citation, dict):
        doc = citation.get('document') or citation.get('document_id') or citation.get('id')
        page = citation.get('page') if 'page' in citation else citation.get('page_number')
        table = citation.get('table') if 'table' in citation else citation.get('table_id')
        return _as_text(doc).lower(), _as_int(page), (_as_text(table).lower() or None)
    if hasattr(citation, 'document_id') or hasattr(citation, 'page_number'):
        doc = (
            getattr(citation, 'document_id', None)
            or getattr(citation, 'document', None)
            or getattr(citation, 'id', None)
        )
        page = getattr(citation, 'page_number', None)
        if page is None:
            page = getattr(citation, 'page', None)
        table = getattr(citation, 'table', None) or getattr(citation, 'table_id', None)
        return _as_text(doc).lower(), _as_int(page), (_as_text(table).lower() or None)
    return _as_text(citation).lower(), None, None


def _number_fields(number: object) -> tuple[str, str, str]:
    if isinstance(number, dict):
        value = number.get('value')
        currency = number.get('currency')
        unit = number.get('unit')
        return _as_text(value), _as_text(currency).upper(), _as_text(unit)
    if hasattr(number, 'value'):
        return (
            _as_text(number.value),
            _as_text(getattr(number, 'currency', '')).upper(),
            _as_text(getattr(number, 'unit', '')),
        )
    return _as_text(number), '', ''


def _values_equal(actual_value: str, expected_value: str) -> bool:
    if actual_value == expected_value:
        return True
    try:
        return float(actual_value.replace(',', '')) == float(expected_value.replace(',', ''))
    except ValueError:
        return False


def _score_number(actual_number: object, expected_number: object) -> bool:
    a_value, a_currency, a_unit = _number_fields(actual_number)
    e_value, e_currency, e_unit = _number_fields(expected_number)
    if not _values_equal(a_value, e_value):
        return False
    if a_currency and a_currency != e_currency:
        return False
    if a_unit and a_unit != e_unit:
        return False
    return True


def _contains_number(actual_numbers: Sequence[object], expected_number: object) -> bool:
    return any(_score_number(item, expected_number) for item in actual_numbers)


def _citation_equal(actual: object, expected: object) -> bool:
    a_doc, a_page, a_table = _citation_fields(actual)
    e_doc, e_page, e_table = _citation_fields(expected)
    if a_doc != e_doc:
        return False
    if a_page != e_page:
        return False
    return not (a_table is not None and e_table is not None and a_table != e_table)


def get_actual_field(actual: object, *names: str, default: object = None) -> object:
    if isinstance(actual, dict):
        for name in names:
            if name in actual and actual.get(name) is not None:
                return actual.get(name)
        return default
    for name in names:
        attr = getattr(actual, name, None)
        if attr is not None:
            return attr
    return default


def score_question(question: object, actual: object) -> QuestionScore:
    record = question if isinstance(question, dict) else getattr(question, 'raw', {})
    if not isinstance(record, dict):
        record = {}
    expected = record.get('expected', {}) if isinstance(record.get('expected'), dict) else {}
    qid = str(record.get('id', getattr(question, 'question_id', '')))

    expected_numbers = list(expected.get('numbers') or [])
    expected_citations = list(expected.get('citations') or [])
    expected_insufficient = bool(expected.get('insufficient_data', False))
    expected_denied = bool(
        expected.get('access_denied', False) or expected.get('accessDenied', False)
    )

    actual_numbers = get_actual_field(actual, 'numbers', 'numbers_found', default=[]) or []
    actual_citations = (
        get_actual_field(actual, 'citations', 'sources', 'citation', default=[]) or []
    )
    if not isinstance(actual_numbers, (list, tuple)):
        actual_numbers = [actual_numbers]
    if not isinstance(actual_citations, (list, tuple)):
        actual_citations = [actual_citations]
    actual_insufficient = bool(
        get_actual_field(actual, 'insufficient_data', 'insufficient', 'no_answer', default=False)
    )
    actual_denied = bool(
        get_actual_field(actual, 'access_denied', 'accessDenied', 'denied', default=False)
    )

    reasons: list[str] = []

    numeric_ok = True
    if expected_numbers:
        missing = [n for n in expected_numbers if not _contains_number(actual_numbers, n)]
        if missing:
            numeric_ok = False
            reasons.append(f'missing numbers: {missing}')

    citation_ok = True
    if expected_citations:
        missing_cites = [
            c
            for c in expected_citations
            if not any(_citation_equal(a, c) for a in actual_citations)
        ]
        if missing_cites:
            citation_ok = False
            reasons.append(f'missing citations: {missing_cites}')
    # For normal answers, an uncited answer fails even if numbers match.
    if (
        not expected_insufficient
        and not expected_denied
        and expected_numbers
        and not actual_citations
        and expected_citations
    ):
        citation_ok = False
        if 'missing citations' not in ' '.join(reasons):
            reasons.append('answer has no citation')

    insufficient_ok = True
    if expected_insufficient:
        if not actual_insufficient:
            insufficient_ok = False
            reasons.append('expected insufficient data')
    # Normal / access cases must not be reported as insufficient.
    elif actual_insufficient and not expected_insufficient:
        insufficient_ok = False
        reasons.append('unexpected insufficient data')

    access_ok = True
    if expected_denied:
        if not actual_denied:
            access_ok = False
            reasons.append('expected access denied')
    elif actual_denied:
        access_ok = False
        reasons.append('unexpected access denied')

    if expected_insufficient:
        passed = insufficient_ok
    elif expected_denied:
        passed = access_ok
    else:
        passed = numeric_ok and citation_ok and (not actual_insufficient) and (not actual_denied)

    numeric_count = len(expected_numbers)
    numeric_passed = sum(1 for n in expected_numbers if _contains_number(actual_numbers, n))
    citation_count = len(expected_citations)
    citation_passed = sum(
        1 for c in expected_citations if any(_citation_equal(a, c) for a in actual_citations)
    )

    numeric_accuracy = (numeric_passed / numeric_count) if numeric_count else 1.0
    citation_accuracy = (citation_passed / citation_count) if citation_count else 1.0

    return QuestionScore(
        question_id=qid,
        passed=passed,
        numeric_ok=numeric_ok,
        citation_ok=citation_ok,
        insufficient_ok=insufficient_ok,
        access_ok=access_ok,
        reasons=tuple(reasons),
        numeric_accuracy=numeric_accuracy,
        citation_accuracy=citation_accuracy,
    )


def load_baseline(profile: str = 'pilot', path: Path | None = None) -> dict[str, object]:
    if path is not None:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return data.get(profile, data) if isinstance(data, dict) else {}
    candidate = PROFILE_BASELINE_FILES.get(profile)
    if candidate is not None and candidate.exists():
        return json.loads(candidate.read_text(encoding='utf-8'))
    # Fall back to shared baseline files.
    for shared in (
        HERE / 'baseline.json',
        HERE / 'baseline.yaml',
        HERE / 'baselines' / 'baseline.json',
    ):
        if shared.exists():
            data = (
                json.loads(shared.read_text(encoding='utf-8')) if shared.suffix == '.json' else None
            )
            if data is None:
                import yaml

                data = yaml.safe_load(shared.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data.get(profile, data) if profile in data else data
    return {}


def aggregate_scores(
    scores: Sequence[QuestionScore], *, total_questions: int | None = None
) -> dict[str, object]:
    score_list = list(scores)
    total = total_questions if total_questions is not None else len(score_list)
    passed = sum(1 for score in score_list if score.passed)
    sum(1 for _ in score_list)  # placeholder count of scored questions
    # Track numeric accuracy over questions that carry expected numbers.
    for _question_score in score_list:
        # Re-derive counts from stored accuracies? Use denominator reconstruction:
        pass
    # We need denominators from questions; track via attributes when available.
    numeric_accuracy = (
        sum(score.numeric_accuracy for score in score_list) / len(score_list) if score_list else 1.0
    )
    citation_accuracy = (
        sum(score.citation_accuracy for score in score_list) / len(score_list)
        if score_list
        else 1.0
    )
    # Weighted correction: compute actual denominators if questions provided.
    # Keep simple mean of per-question rates as a robust fallback.
    return {
        'total_questions': total,
        'scored_questions': len(score_list),
        'passed': passed,
        'failed': len(score_list) - passed,
        'pass_rate': (passed / len(score_list)) if score_list else 1.0,
        'numeric_accuracy': numeric_accuracy,
        'citation_accuracy': citation_accuracy,
        'answer_coverage': (passed / len(score_list)) if score_list else 1.0,
    }


def aggregate_with_questions(
    questions: Sequence[object],
    scores: Sequence[QuestionScore],
) -> dict[str, object]:
    """Aggregate using the expected-answer denominators from the questions."""
    score_by_id = {score.question_id: score for score in scores}
    numeric_total = 0
    numeric_passed = 0
    citation_total = 0
    citation_passed = 0
    sufficient_total = 0
    sufficient_passed = 0
    for question in questions:
        record = question if isinstance(question, dict) else getattr(question, 'raw', {})
        if not isinstance(record, dict):
            continue
        expected = record.get('expected', {}) if isinstance(record.get('expected'), dict) else {}
        qid = str(record.get('id', ''))
        score = score_by_id.get(qid)
        if score is None:
            continue
        expected_numbers = list(expected.get('numbers') or [])
        expected_citations = list(expected.get('citations') or [])
        if expected_numbers:
            numeric_total += len(expected_numbers)
            numeric_passed += round(score.numeric_accuracy * len(expected_numbers))
        if expected_citations:
            citation_total += len(expected_citations)
            citation_passed += round(score.citation_accuracy * len(expected_citations))
        if expected.get('insufficient_data'):
            sufficient_total += 1
            if score.insufficient_ok:
                sufficient_passed += 1

    passed = sum(1 for score in scores if score.passed)
    total = len(scores)
    numeric_accuracy = (numeric_passed / numeric_total) if numeric_total else 1.0
    citation_accuracy = (citation_passed / citation_total) if citation_total else 1.0
    return {
        'total_questions': len(questions),
        'scored_questions': total,
        'passed': passed,
        'failed': total - passed,
        'pass_rate': (passed / total) if total else 1.0,
        'numeric_accuracy': numeric_accuracy,
        'citation_accuracy': citation_accuracy,
        'answer_coverage': (passed / total) if total else 1.0,
        'numeric_total': numeric_total,
        'numeric_passed': numeric_passed,
        'citation_total': citation_total,
        'citation_passed': citation_passed,
        'insufficient_total': sufficient_total,
        'insufficient_passed': sufficient_passed,
    }


def compare_to_baseline(
    report: dict[str, object],
    baseline: dict[str, object] | None,
) -> tuple[bool, list[str]]:
    if not baseline:
        return True, ['No baseline available; skipping regression check.']
    thresholds = {}
    # Load thresholds from questions dir if possible.
    try:
        try:
            import run_golden
        except Exception:
            with contextlib.suppress(Exception):
                from . import run_golden

        thresholds = run_golden.load_thresholds()
    except Exception:
        thresholds = {}
    messages: list[str] = []
    ok = True

    numeric_threshold = float(
        thresholds.get('numeric_accuracy', baseline.get('numeric_accuracy', 0.95))
    )
    citation_threshold = float(
        thresholds.get('citation_accuracy', baseline.get('citation_accuracy', 1.0))
    )
    measured_numeric = float(report.get('numeric_accuracy', 0.0))
    measured_citation = float(report.get('citation_accuracy', 0.0))

    if measured_numeric < numeric_threshold:
        ok = False
        messages.append(
            f'numeric_accuracy {measured_numeric:.4f} below threshold {numeric_threshold:.4f}'
        )
    else:
        messages.append(f'numeric_accuracy OK ({measured_numeric:.4f} >= {numeric_threshold:.4f})')

    if measured_citation < citation_threshold:
        ok = False
        messages.append(
            f'citation_accuracy {measured_citation:.4f} below threshold {citation_threshold:.4f}'
        )
    else:
        messages.append(
            f'citation_accuracy OK ({measured_citation:.4f} >= {citation_threshold:.4f})'
        )

    # Baseline drop check (beyond agreed threshold).
    baseline_numeric = baseline.get('numeric_accuracy')
    baseline_citation = baseline.get('citation_accuracy')
    tolerance = float(baseline.get('tolerance', 0.0))
    if baseline_numeric is not None and measured_numeric < float(baseline_numeric) - tolerance:
        ok = False
        messages.append(
            f'numeric_accuracy {measured_numeric:.4f} dropped below baseline {float(baseline_numeric):.4f}'
        )
    if baseline_citation is not None and measured_citation < float(baseline_citation) - tolerance:
        ok = False
        messages.append(
            f'citation_accuracy {measured_citation:.4f} dropped below baseline {float(baseline_citation):.4f}'
        )

    # Question count regression.
    baseline_count = baseline.get('question_count') or baseline.get('minimum_questions')
    if baseline_count is not None and int(report.get('question_count', 0)) < int(baseline_count):
        ok = False
        messages.append('question count dropped below baseline')
    return ok, messages


def build_baseline_report(profile: str = 'pilot') -> dict[str, object]:
    try:
        import run_golden
    except Exception:
        from . import run_golden

    report = run_golden.run_golden(profile=profile)
    questions = run_golden.load_questions()
    scores = report['scores']
    summary = aggregate_with_questions(questions, scores)
    return {
        'profile': profile,
        'environment': run_golden.profile_to_environment(profile),
        'numeric_accuracy': summary['numeric_accuracy'],
        'citation_accuracy': summary['citation_accuracy'],
        'answer_coverage': summary['answer_coverage'],
        'pass_rate': summary['pass_rate'],
        'passed': summary['passed'],
        'total': summary['scored_questions'],
        'question_count': summary['total_questions'],
        'numeric_total': summary['numeric_total'],
        'numeric_passed': summary['numeric_passed'],
        'citation_total': summary['citation_total'],
        'citation_passed': summary['citation_passed'],
        'tolerance': 0.0,
    }


# Compatibility alias expected by some callers.
aggregate = aggregate_scores
score = score_question
