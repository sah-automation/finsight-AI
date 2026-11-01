"""Golden set runner for pilot and standard configurations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

HERE = Path(__file__).resolve().parent
if TYPE_CHECKING:
    from collections.abc import Callable

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


def _expected_by_question(questions: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        q_text = str(question.get('question', '')).strip()
        expected = question.get('expected', {})
        if not isinstance(expected, dict):
            expected = {}
        expected = dict(expected)
        result[q_text] = expected
        role = None if question.get('role') is None else str(question.get('role')).strip()
        company = (
            'company-a' if question.get('company') is None else str(question.get('company')).strip()
        )
        result[(q_text, role, company)] = expected
        result[(q_text, role, None)] = expected
        qid = question.get('id')
        if qid is not None:
            result[str(qid)] = dict(expected)
    return result


def _make_real_ask(
    *,
    profile: str,
    config: object,
    questions: list[dict[str, object]],
) -> Callable[[object], object]:
    expected_map = _expected_by_question(questions)

    try:
        from deterministic_adapters import (
            DeterministicHybridSearch,
            DeterministicInputGate,
            DeterministicLLMGateway,
            DeterministicMetricRepository,
            DeterministicReranker,
            FixedEmbeddingProvider,
            set_current_context,
        )
    except Exception:
        from tests.golden.deterministic_adapters import (
            DeterministicHybridSearch,
            DeterministicInputGate,
            DeterministicLLMGateway,
            DeterministicMetricRepository,
            DeterministicReranker,
            FixedEmbeddingProvider,
            set_current_context,
        )

    from finsight.composition import build_composition_root

    answer_cache_cls = None
    try:
        from finsight.adapters.cache.answer_cache import AnswerCache as _AnswerCache

        answer_cache_cls = _AnswerCache
    except Exception:  # pragma: no cover
        answer_cache_cls = None

    cache = None
    if answer_cache_cls is not None:
        table_name = f'golden-{profile}-answer-cache'
        try:
            from finsight.adapters.cache.answer_cache import _TABLES

            _TABLES.pop(table_name, None)
        except Exception:
            pass
        cache = answer_cache_cls(table_name=table_name)

    container = build_composition_root(
        config=config,
        mode=profile,
        llm_gateway=DeterministicLLMGateway(expected_map),
        embedding_provider=FixedEmbeddingProvider(),
        hybrid_search=DeterministicHybridSearch(expected_map),
        input_gate=DeterministicInputGate(expected_map),
        reranker=DeterministicReranker(),
        metric_repository=DeterministicMetricRepository(expected_map),
        answer_cache=cache,
    )
    ask_use_case = getattr(container, 'ask_question_use_case', None)
    if ask_use_case is None:
        ask_use_case = getattr(container, 'ask', None)
    if ask_use_case is None:
        raise RuntimeError('Composition container did not expose an ask use case.')

    def _ask(question: object) -> object:
        record: dict[str, object] = {}
        if isinstance(question, dict):
            record = dict(question)
        elif hasattr(question, 'raw') and isinstance(question.raw, dict):
            record = dict(question.raw)
        expected = record.get('expected')
        if not isinstance(expected, dict):
            expected = expected_map.get(str(record.get('question', '')).strip(), {})
        if not isinstance(expected, dict):
            expected = {}

        q_text = str(
            record.get('question')
            or record.get('query')
            or record.get('q')
            or getattr(question, 'question', '')
            or ''
        ).strip()
        company = record.get('company', 'company-a')
        if company is None:
            company = 'company-a'

        set_current_context(question=q_text, role=record.get('role'), company=company)
        try:
            result = _call_use_case(
                ask_use_case,
                {
                    'company_id': company,
                    'question': q_text or str(question),
                    'role': record.get('role'),
                    'access_scope': record.get('access_scope'),
                },
            )
        except Exception as exc:
            if 'access' in str(exc).lower() or 'denied' in str(exc).lower():
                from types import SimpleNamespace

                return SimpleNamespace(
                    access_denied=True,
                    insufficient_data=False,
                    numbers=[],
                    citations=[],
                    answer=None,
                )
            raise
        return result

    return _ask


def _run_maybe_awaitable(value: object) -> object:
    """Resolve a possibly-awaitable value into its concrete result.

    Ask-question use cases are asynchronous, but the golden runner drives them
    synchronously.  A coroutine (or any awaitable) is driven to completion here
    so that the real ask flow can be exercised end-to-end.
    """
    import asyncio
    import inspect

    if not inspect.isawaitable(value):
        return value

    import inspect

    # ``asyncio.run`` only accepts a coroutine object, so normalise any other
    # awaitable (e.g. a task or awaitable iterator) into one first.
    if not inspect.iscoroutine(value):

        async def _resolve() -> object:
            return await value  # type: ignore[misc]

        coroutine = _resolve()
    else:
        coroutine = value

    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if running:
        # Avoid "cannot be called when another loop is running" by offloading.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coroutine)
            return future.result()
    return asyncio.run(coroutine)


def _call_use_case(use_case: object, payload: dict[str, object]) -> object:
    for method_name in ('run', 'execute', 'ask', 'answer', 'handle', 'process', '__call__'):
        method = getattr(use_case, method_name, None)
        if not callable(method):
            continue
        try:
            return _run_maybe_awaitable(method(payload))
        except TypeError:
            try:
                return _run_maybe_awaitable(method(**payload))
            except TypeError:
                continue
    if callable(use_case):
        return _run_maybe_awaitable(use_case(payload))
    raise RuntimeError('Ask use case is not callable.')


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

    if ask is not None:
        ask_fn = ask
    else:
        ask_fn = _make_real_ask(profile=profile, config=config, questions=questions)

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
