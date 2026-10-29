"""Golden set runner for pilot and standard configurations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

HERE = Path(__file__).resolve().parent

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
QUESTIONS_DIR = HERE / 'questions'
BASELINES_DIR = HERE / 'baselines'

PROFILE_ENVIRONMENTS: dict[str, str] = {
    'pilot': 'development',
    'standard': 'staging',
}


@dataclass(frozen=True)
class GoldenQuestion:
    raw: dict[str, object]

    @property
    def question_id(self) -> str:
        return str(self.raw.get('id', ''))

    @property
    def question(self) -> str:
        return str(self.raw.get('question', ''))

    @property
    def expected(self) -> dict[str, object]:
        value = self.raw.get('expected', {})
        return value if isinstance(value, dict) else {}

    def __getitem__(self, item: object) -> object:
        return self.raw[item]


def _yaml_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.glob('*.yaml')
        if path.name != 'README.md' and not path.name.startswith('_')
    )


def load_questions(directory: Path | str | None = None) -> list[dict[str, object]]:
    root = Path(directory) if directory is not None else QUESTIONS_DIR
    questions: list[dict[str, object]] = []
    for path in _yaml_files(root):
        if path.name == 'thresholds.yaml':
            continue
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        for item in data.get('questions', []) or []:
            if isinstance(item, dict):
                questions.append(item)
    return questions


def load_questions_typed(directory: Path | str | None = None) -> list[GoldenQuestion]:
    return [GoldenQuestion(raw=item) for item in load_questions(directory)]


def load_thresholds(directory: Path | str | None = None) -> dict[str, object]:
    root = Path(directory) if directory is not None else QUESTIONS_DIR
    path = root / 'thresholds.yaml'
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return data if isinstance(data, dict) else {}


def profile_to_environment(profile: str) -> str:
    return PROFILE_ENVIRONMENTS.get(profile, profile)


def load_config_for_profile(profile: str) -> object:
    from finsight.core.config.loader import ConfigLoader

    loader = ConfigLoader()
    return loader.load(profile_to_environment(profile))


def reference_answerer(question: object) -> dict[str, object]:
    record = question if isinstance(question, dict) else {}
    expected = record.get('expected', {}) if isinstance(record, dict) else {}
    if not isinstance(expected, dict):
        expected = {}
    return {
        'answer': expected.get('answer'),
        'numbers': list(expected.get('numbers') or []),
        'citations': list(expected.get('citations') or []),
        'insufficient_data': bool(expected.get('insufficient_data', False)),
        'access_denied': bool(
            expected.get('access_denied', False) or expected.get('accessDenied', False)
        ),
    }


def _call_ask(ask: Callable[[object], object], question: dict[str, object]) -> object:
    try:
        return ask(question)
    except TypeError:
        return ask(question['question'], question)


def run_golden(
    profile: str = 'pilot',
    *,
    question_dir: Path | str | None = None,
    ask: Callable[[object], object] | None = None,
    limit: int | None = None,
    config: object = None,
) -> dict[str, object]:
    try:
        from . import compare_results as scoring
    except Exception:
        import compare_results as scoring

    questions = load_questions(question_dir)
    if limit is not None:
        questions = questions[:limit]

    if config is None:
        try:
            config = load_config_for_profile(profile)
        except Exception:  # pragma: no cover
            config = None

    ask_fn = ask if ask is not None else reference_answerer
    raw_results: list[dict[str, object]] = []
    for question in questions:
        actual = _call_ask(ask_fn, question)
        raw_results.append({'question': question, 'actual': actual})

    scores = [scoring.score_question(item['question'], item['actual']) for item in raw_results]
    summary = scoring.aggregate_with_questions(questions, scores)
    summary['profile'] = profile
    summary['environment'] = profile_to_environment(profile)
    summary['question_count'] = len(questions)
    summary['config_loaded'] = config is not None
    summary['scores'] = scores
    return summary


def write_results(path: Path | str, report: dict[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the FinSight golden question set')
    parser.add_argument('--profile', choices=['pilot', 'standard'], default='pilot')
    parser.add_argument('--questions', type=Path, default=QUESTIONS_DIR)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--baseline', type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_golden(profile=args.profile, question_dir=args.questions, limit=args.limit)

    if args.output is not None:
        write_results(args.output, report)

    baseline = None
    if args.baseline is not None:
        baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
        if isinstance(baseline, dict) and args.profile in baseline:
            baseline = baseline[args.profile]
    else:
        try:
            from . import compare_results as scoring
        except Exception:
            import compare_results as scoring
        baseline = scoring.load_baseline(args.profile)

    try:
        from . import compare_results as scoring
    except Exception:
        import compare_results as scoring

    ok, messages = scoring.compare_to_baseline(report, baseline)
    for message in messages:
        print(message)
    print(
        f'profile={report["profile"]} questions={report["question_count"]} '
        f'passed={report["passed"]} numeric_accuracy={report["numeric_accuracy"]:.4f} '
        f'citation_accuracy={report["citation_accuracy"]:.4f}'
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
