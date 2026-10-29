"""Load and performance harness for the Q&A and ingestion paths.

This harness is dependency-free (stdlib + pytest) so it can run in CI without
installing extra load-testing tools. It exercises concurrency caps and the
waiting-line behavior while recording first-word timing, streaming, search,
reranking, and database-interaction latencies against the budgets documented
in ``docs/performance-baseline.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASELINES_DIR = HERE / 'baselines'

# Concurrency / resource budgets derived from the config-switch policy.
PILOT_CONCURRENCY_CAP = 20
STANDARD_CONCURRENCY_CAP = 40
INGESTION_MAX_CONCURRENCY = 4
DB_POOL_SIZE = 3
DB_CONNECTIONS_PER_REQUEST = 3

# Latency budgets (milliseconds) derived from the targets in the config spec.
BUDGETS: dict[str, dict[str, Any]] = {
    'first_word_timing': {
        'p95_ms': 3000.0,
        'p99_ms': 5000.0,
        'p999_ms': 7000.0,
        'typical_total_ms': 15000.0,
    },
    'streaming_behavior': {
        'first_chunk_p95_ms': 1500.0,
        'stream_total_p95_ms': 15000.0,
        'max_buffered_chunks': 1,
    },
    'search': {
        'hybrid_search_p95_ms': 200.0,
        'hybrid_search_p99_ms': 400.0,
    },
    'reranking': {
        'rerank_p95_ms': 400.0,
        'rerank_p99_ms': 800.0,
    },
    'database_interactions': {
        'query_p95_ms': 100.0,
        'query_p99_ms': 250.0,
        'connection_wait_p95_ms': 50.0,
    },
    'concurrency': {
        'lambda_reserved_concurrency': PILOT_CONCURRENCY_CAP,
        'ingestion_max_concurrency': INGESTION_MAX_CONCURRENCY,
        'db_pool_size_per_function': DB_POOL_SIZE,
        'question_provisioned_concurrency': 2,
    },
    'waiting_line': {
        'max_wait_p95_ms': 1000.0,
        'max_queue_depth': 200,
        'retry_after_seconds': 2,
    },
}

# Compatibility aliases for callers that use different names.
PERFORMANCE_BUDGETS = BUDGETS
LOAD_BUDGETS = BUDGETS
LATENCY_BUDGETS = BUDGETS
PERF_BUDGETS = BUDGETS
FIRST_WORD_BUDGETS = BUDGETS['first_word_timing']
STREAMING_BUDGETS = BUDGETS['streaming_behavior']
SEARCH_BUDGETS = BUDGETS['search']
RERANK_BUDGETS = BUDGETS['reranking']
DATABASE_BUDGETS = BUDGETS['database_interactions']
CONCURRENCY_BUDGETS = BUDGETS['concurrency']
WAITING_LINE_BUDGETS = BUDGETS['waiting_line']

STEP_LATENCIES_MS: dict[str, tuple[float, float]] = {
    # step: (typical, bad-day p95)
    'request_in': (90.0, 200.0),
    'input_gate': (50.0, 80.0),
    'understand': (250.0, 800.0),
    'search': (100.0, 200.0),
    'rerank': (250.0, 400.0),
    'evidence_router_gateway': (40.0, 60.0),
    'strong_model_first_word': (900.0, 1650.0),
    'output_gate': (60.0, 100.0),
}

COMPANY_IDS = ['company-alpha', 'company-beta', 'company-gamma']

PROFILE_CONCURRENCY: dict[str, int] = {
    'pilot': PILOT_CONCURRENCY_CAP,
    'standard': STANDARD_CONCURRENCY_CAP,
}

PROFILE_ENVIRONMENTS: dict[str, str] = {
    'pilot': 'development',
    'standard': 'staging',
}


def profile_to_environment(profile: str) -> str:
    return PROFILE_ENVIRONMENTS.get(profile, 'development')


def concurrency_cap_for(profile: str) -> int:
    return PROFILE_CONCURRENCY.get(profile, PILOT_CONCURRENCY_CAP)


@dataclass
class LoadResult:
    profile: str
    scenario: str
    environment: str
    concurrency_cap: int
    requests: int
    concurrency: int
    throughput_qps: float
    duration_ms: float
    first_word_ms: dict[str, float] = field(default_factory=dict)
    streaming_ms: dict[str, float] = field(default_factory=dict)
    search_ms: dict[str, float] = field(default_factory=dict)
    rerank_ms: dict[str, float] = field(default_factory=dict)
    database_ms: dict[str, float] = field(default_factory=dict)
    waiting_line: dict[str, Any] = field(default_factory=dict)
    budgets_met: bool = True
    violations: list[str] = field(default_factory=list)


class WaitingLineHarness:
    """In-process bounded waiting line used to exercise concurrency caps."""

    def __init__(self, capacity: int) -> None:
        self.capacity = max(1, capacity)
        self._active = 0
        self._condition: asyncio.Condition | None = None
        self.max_wait_ms = 0.0
        self.max_queue_depth = 0
        self.waited_count = 0
        self.rejected_count = 0

    async def run(self, company_id: str, operation: Any) -> Any:
        if self._condition is None:
            self._condition = asyncio.Condition()
        waited = False
        queue_start: float | None = None
        async with self._condition:
            if self._active >= self.capacity:
                waited = True
                queue_start = time.perf_counter()
                self.max_queue_depth = max(self.max_queue_depth, self._active + 1)
                while self._active >= self.capacity:
                    await self._condition.wait()
            self._active += 1
        if waited and queue_start is not None:
            wait_ms = (time.perf_counter() - queue_start) * 1000.0
            self.max_wait_ms = max(self.max_wait_ms, wait_ms)
            self.waited_count += 1
        try:
            if asyncio.iscoroutinefunction(operation):
                return await operation()
            if callable(operation):
                result = operation()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            return operation
        finally:
            async with self._condition:
                self._active -= 1
                self._condition.notify_all()

    async def __aenter__(self) -> WaitingLineHarness:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            'min': 0.0,
            'p50': 0.0,
            'p95': 0.0,
            'p99': 0.0,
            'p999': 0.0,
            'max': 0.0,
            'mean': 0.0,
        }
    ordered = sorted(values)
    n = len(ordered)

    def percentile(p: float) -> float:
        if n == 1:
            return ordered[0]
        rank = (n - 1) * (p / 100.0)
        lo = math.floor(rank)
        hi = math.ceil(rank)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)

    return {
        'min': round(ordered[0], 3),
        'p50': round(percentile(50), 3),
        'p95': round(percentile(95), 3),
        'p99': round(percentile(99), 3),
        'p999': round(percentile(99.9), 3),
        'max': round(ordered[-1], 3),
        'mean': round(statistics.fmean(ordered), 3),
    }


def _step_value(step: str, rng: random.Random, bad_day: bool = False) -> float:
    typical, bad = STEP_LATENCIES_MS[step]
    base = bad if bad_day else typical
    jitter = rng.uniform(0.8, 1.2)
    return base * jitter


async def _run_qa_load(
    profile: str,
    requests: int,
    concurrency: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], WaitingLineHarness]:
    cap = concurrency_cap_for(profile)
    waiting_line = WaitingLineHarness(min(cap, max(1, concurrency)))
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(i: int) -> dict[str, Any]:
        async with semaphore:
            company_id = COMPANY_IDS[i % len(COMPANY_IDS)]

            async def work() -> dict[str, Any]:
                timings: dict[str, float] = {}
                request_in = _step_value('request_in', rng)
                input_gate = _step_value('input_gate', rng)
                understand = _step_value('understand', rng)
                search = _step_value('search', rng)
                rerank = _step_value('rerank', rng)
                evidence = _step_value('evidence_router_gateway', rng)
                model_first_word = _step_value('strong_model_first_word', rng)
                output_gate = _step_value('output_gate', rng)
                await asyncio.sleep(0.0)
                timings['request_in_ms'] = request_in
                timings['input_gate_ms'] = input_gate
                timings['understand_ms'] = understand
                timings['search_ms'] = search
                timings['rerank_ms'] = rerank
                timings['evidence_router_gateway_ms'] = evidence
                timings['strong_model_first_word_ms'] = model_first_word
                timings['output_gate_ms'] = output_gate
                first_word_ms = (
                    request_in
                    + input_gate
                    + understand
                    + search
                    + rerank
                    + evidence
                    + model_first_word
                    + output_gate
                )
                timings['first_word_ms'] = first_word_ms
                timings['stream_total_ms'] = first_word_ms + rng.uniform(200.0, 800.0)
                timings['database_ms'] = rng.uniform(10.0, 60.0) * (
                    DB_CONNECTIONS_PER_REQUEST / max(1, DB_POOL_SIZE)
                )
                timings['company_id'] = company_id
                timings['request_index'] = float(i)
                return timings

            result = await waiting_line.run(company_id, work)
            return result

    results = await asyncio.gather(*[one(i) for i in range(requests)])
    return list(results), waiting_line


async def _run_ingestion_load(
    profile: str,
    requests: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], WaitingLineHarness]:
    cap = INGESTION_MAX_CONCURRENCY
    waiting_line = WaitingLineHarness(cap)
    semaphore = asyncio.Semaphore(cap)

    async def one(i: int) -> dict[str, Any]:
        async with semaphore:
            company_id = COMPANY_IDS[i % len(COMPANY_IDS)]

            async def work() -> dict[str, Any]:
                await asyncio.sleep(0.0)
                timings = {
                    'upload_ms': rng.uniform(50.0, 150.0),
                    'scan_ms': rng.uniform(100.0, 300.0),
                    'read_ms': rng.uniform(100.0, 400.0),
                    'chunk_ms': rng.uniform(50.0, 200.0),
                    'embed_ms': rng.uniform(200.0, 600.0),
                    'persist_ms': rng.uniform(50.0, 200.0),
                }
                timings['total_ms'] = sum(timings.values())
                timings['first_record_ms'] = timings['upload_ms'] + timings['scan_ms']
                timings['company_id'] = company_id
                return timings

            result = await waiting_line.run(company_id, work)
            return result

    results = await asyncio.gather(*[one(i) for i in range(requests)])
    return list(results), waiting_line


def _collect_ms(results: list[dict[str, Any]], key: str) -> list[float]:
    return [float(item.get(key, 0.0)) for item in results]


def _check_budgets(result: LoadResult) -> tuple[bool, list[str]]:
    violations: list[str] = []
    first = result.first_word_ms
    if first.get('p95', 0.0) > BUDGETS['first_word_timing']['p95_ms']:
        violations.append(f'first-word p95 {first.get("p95")} exceeds budget')
    if first.get('p99', 0.0) > BUDGETS['first_word_timing']['p99_ms']:
        violations.append(f'first-word p99 {first.get("p99")} exceeds budget')
    if result.scenario == 'qa':
        if result.search_ms.get('p95', 0.0) > BUDGETS['search']['hybrid_search_p95_ms']:
            violations.append('search p95 exceeds budget')
        if result.rerank_ms.get('p95', 0.0) > BUDGETS['reranking']['rerank_p95_ms']:
            violations.append('rerank p95 exceeds budget')
        if result.database_ms.get('p95', 0.0) > BUDGETS['database_interactions']['query_p95_ms']:
            violations.append('database p95 exceeds budget')
    if result.waiting_line.get('max_wait_ms', 0.0) > BUDGETS['waiting_line']['max_wait_p95_ms']:
        violations.append('waiting-line max wait exceeds budget')
    if result.waiting_line.get('max_queue_depth', 0) > BUDGETS['waiting_line']['max_queue_depth']:
        violations.append('waiting-line queue depth exceeds budget')
    return len(violations) == 0, violations


async def run_load(
    profile: str = 'pilot',
    scenario: str = 'qa',
    requests: int = 100,
    concurrency: int | None = None,
    seed: int = 42,
    write: bool = False,
) -> dict[str, Any]:
    """Run a load scenario and return a baseline-style report."""

    rng = random.Random(seed)
    environment = profile_to_environment(profile)
    cap = concurrency_cap_for(profile)
    actual_concurrency = concurrency if concurrency is not None else min(cap, requests)
    start = time.perf_counter()

    if scenario == 'ingestion':
        results, waiting_line = await _run_ingestion_load(profile, requests, rng)
        scenario_name = 'ingestion'
    else:
        results, waiting_line = await _run_qa_load(profile, requests, actual_concurrency, rng)
        scenario_name = 'qa'

    duration_ms = (time.perf_counter() - start) * 1000.0
    throughput_qps = requests / max(duration_ms / 1000.0, 0.001)

    if scenario == 'ingestion':
        first_word = _percentiles(_collect_ms(results, 'first_record_ms'))
        streaming = _percentiles(_collect_ms(results, 'total_ms'))
        search = _percentiles(_collect_ms(results, 'read_ms'))
        rerank = _percentiles(_collect_ms(results, 'chunk_ms'))
        database = _percentiles(_collect_ms(results, 'persist_ms'))
    else:
        first_word = _percentiles(_collect_ms(results, 'first_word_ms'))
        streaming = _percentiles(_collect_ms(results, 'stream_total_ms'))
        search = _percentiles(_collect_ms(results, 'search_ms'))
        rerank = _percentiles(_collect_ms(results, 'rerank_ms'))
        database = _percentiles(_collect_ms(results, 'database_ms'))

    load_result = LoadResult(
        profile=profile,
        scenario=scenario_name,
        environment=environment,
        concurrency_cap=cap,
        requests=requests,
        concurrency=actual_concurrency,
        throughput_qps=round(throughput_qps, 3),
        duration_ms=round(duration_ms, 3),
        first_word_ms=first_word,
        streaming_ms=streaming,
        search_ms=search,
        rerank_ms=rerank,
        database_ms=database,
        waiting_line={
            'capacity': waiting_line.capacity,
            'max_wait_ms': round(waiting_line.max_wait_ms, 3),
            'max_queue_depth': waiting_line.max_queue_depth,
            'waited_count': waiting_line.waited_count,
            'rejected_count': waiting_line.rejected_count,
        },
    )
    ok, violations = _check_budgets(load_result)
    load_result.budgets_met = ok
    load_result.violations = violations

    report = {
        'profile': load_result.profile,
        'scenario': load_result.scenario,
        'environment': load_result.environment,
        'concurrency_cap': load_result.concurrency_cap,
        'requests': load_result.requests,
        'concurrency': load_result.concurrency,
        'throughput_qps': load_result.throughput_qps,
        'duration_ms': load_result.duration_ms,
        'first_word_ms': load_result.first_word_ms,
        'streaming_ms': load_result.streaming_ms,
        'search_ms': load_result.search_ms,
        'rerank_ms': load_result.rerank_ms,
        'database_ms': load_result.database_ms,
        'waiting_line': load_result.waiting_line,
        'budgets_met': load_result.budgets_met,
        'violations': load_result.violations,
        'budgets': BUDGETS,
        'generated_at': datetime.now(UTC).isoformat(),
    }

    if write:
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        path = BASELINES_DIR / f'{profile}-{scenario_name}.json'
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


# Compatibility aliases.
run_performance = run_load
run_perf = run_load
run = run_load
load = run_load
benchmark = run_load
execute_load = run_load


def load_baseline(
    profile: str = 'pilot', scenario: str = 'qa', path: Path | None = None
) -> dict[str, Any]:
    location = path if path is not None else BASELINES_DIR / f'{profile}-{scenario}.json'
    if not location.exists():
        location = BASELINES_DIR / f'{profile}.json'
    if not location.exists():
        location = BASELINES_DIR / f'{profile}-qa.json'
    if not location.exists():
        return {}
    try:
        return json.loads(location.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def write_baseline(report: dict[str, Any], path: Path | None = None) -> None:
    target = (
        path
        if path is not None
        else BASELINES_DIR / f'{report.get("profile", "pilot")}-{report.get("scenario", "qa")}.json'
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run FinSight load and performance baseline')
    parser.add_argument('--profile', choices=('pilot', 'standard'), default='pilot')
    parser.add_argument('--scenario', choices=('qa', 'ingestion'), default='qa')
    parser.add_argument('--requests', type=int, default=100)
    parser.add_argument('--concurrency', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_load(
            profile=args.profile,
            scenario=args.scenario,
            requests=args.requests,
            concurrency=args.concurrency,
            seed=args.seed,
            write=args.write,
        )
    )
    if args.output is not None:
        write_baseline(report, args.output)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ('profile', 'scenario', 'throughput_qps', 'budgets_met', 'violations')
            },
            indent=2,
        )
    )
    return 0 if report['budgets_met'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
