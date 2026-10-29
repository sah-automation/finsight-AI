"""Tests for the golden scoring harness itself (not the full Q&A flow)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_results
import run_golden

pytestmark = [pytest.mark.golden]


def test_question_set_has_minimum_size() -> None:
    questions = run_golden.load_questions()
    assert len(questions) >= 100


def test_question_ids_are_unique() -> None:
    questions = run_golden.load_questions()
    ids = [q['id'] for q in questions]
    assert len(ids) == len(set(ids))


def test_thresholds_loaded() -> None:
    thresholds = run_golden.load_thresholds()
    assert thresholds['numeric_accuracy'] >= 0.9
    assert thresholds['citation_accuracy'] >= 0.9


def test_loads_both_profiles() -> None:
    assert run_golden.profile_to_environment('pilot') == 'development'
    assert run_golden.profile_to_environment('standard') == 'staging'


def test_config_loads_for_both_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        'VECTOR_DB_HOST',
        'VECTOR_DB_NAME',
        'VECTOR_DB_USER',
        'VECTOR_DB_PASSWORD',
        'ANSWER_CACHE_TABLE',
        'ROLE_CACHE_TABLE',
        'INGESTION_QUEUE_URL',
        'REPROCESSING_QUEUE_URL',
        'REPORTS_QUEUE_URL',
        'DLQ_URL',
        'AWS_REGION',
        'COGNITO_CLIENT_ID',
        'COGNITO_USER_POOL_ID',
        'DOCUMENTS_BUCKET',
        'REPORTS_BUCKET',
        'BACKUPS_BUCKET',
        'METERING_TABLE',
        'OTLP_ENDPOINT',
        'SOURCE_VIEWER_SIGNING_KEY',
    ):
        monkeypatch.setenv(key, 'test-value')
    for profile in ('pilot', 'standard'):
        config = run_golden.load_config_for_profile(profile)
        assert config is not None


def test_reference_answerer_scores_perfectly() -> None:
    report = run_golden.run_golden(profile='pilot', ask=run_golden.reference_answerer)
    assert report['passed'] == report['question_count']
    assert report['numeric_accuracy'] >= 0.95
    assert report['citation_accuracy'] >= 1.0


def test_same_set_runs_on_both_profiles() -> None:
    pilot = run_golden.run_golden(profile='pilot')
    standard = run_golden.run_golden(profile='standard')
    assert pilot['question_count'] == standard['question_count']


def test_scoring_uses_citation_and_numeric_not_exact_string() -> None:
    q = next(item for item in run_golden.load_questions() if item['expected'].get('numbers'))
    # Change answer prose but keep numbers and citations.
    actual = {
        'answer': 'totally different prose ' + str(q['expected']['numbers'][0]['value']),
        'numbers': list(q['expected']['numbers']),
        'citations': list(q['expected']['citations']),
        'insufficient_data': False,
        'access_denied': False,
    }
    score = compare_results.score_question(q, actual)
    assert score.passed is True
    assert score.numeric_ok is True
    assert score.citation_ok is True


def test_wrong_citation_fails_question() -> None:
    q = next(item for item in run_golden.load_questions() if item['expected'].get('citations'))
    actual = {
        'answer': q['expected'].get('answer'),
        'numbers': list(q['expected'].get('numbers') or []),
        'citations': [],
        'insufficient_data': False,
        'access_denied': False,
    }
    score = compare_results.score_question(q, actual)
    assert score.passed is False
    assert score.citation_ok is False


def test_baseline_exists_for_both_profiles() -> None:
    for profile in ('pilot', 'standard'):
        baseline = compare_results.load_baseline(profile)
        assert baseline, f'missing baseline for {profile}'
        assert 'numeric_accuracy' in baseline
        assert 'citation_accuracy' in baseline


def test_compare_to_baseline_passes_for_reference_run() -> None:
    for profile in ('pilot', 'standard'):
        report = run_golden.run_golden(profile=profile)
        baseline = compare_results.load_baseline(profile)
        ok, messages = compare_results.compare_to_baseline(report, baseline)
        assert ok, messages


def test_regression_check_fails_on_drop() -> None:
    report = {'numeric_accuracy': 0.1, 'citation_accuracy': 0.1, 'question_count': 1}
    baseline = {'numeric_accuracy': 1.0, 'citation_accuracy': 1.0, 'question_count': 10}
    ok, messages = compare_results.compare_to_baseline(report, baseline)
    assert ok is False
    assert messages


def test_baseline_files_written() -> None:
    assert (HERE / 'baselines' / 'pilot.json').exists()
    assert (HERE / 'baselines' / 'standard.json').exists()
    assert (HERE / 'baseline.json').exists()


def test_write_results(tmp_path: Path) -> None:
    report = run_golden.run_golden(profile='pilot', limit=3)
    target = tmp_path / 'out.json'
    run_golden.write_results(target, report)
    data = json.loads(target.read_text())
    assert data['question_count'] == 3


def test_gallery_insufficient_case_passes() -> None:
    q = next(
        item for item in run_golden.load_questions() if item['expected'].get('insufficient_data')
    )
    actual = {
        'answer': None,
        'numbers': [],
        'citations': [],
        'insufficient_data': True,
        'access_denied': False,
    }
    score = compare_results.score_question(q, actual)
    assert score.passed is True


def test_access_denied_case_passes() -> None:
    q = next(item for item in run_golden.load_questions() if item['expected'].get('access_denied'))
    actual = {
        'answer': None,
        'numbers': [],
        'citations': [],
        'insufficient_data': False,
        'access_denied': True,
    }
    score = compare_results.score_question(q, actual)
    assert score.passed is True
