# Performance and load baseline - Q&A and ingestion

Baseline established by issue #79. The machine-readable budgets live in
`tests/performance/performance_harness.py` (`BUDGETS`) and the recorded
baselines live under `tests/performance/baselines/`.

## Running the harness

```bash
uv run python tests/performance/performance_harness.py \
  --profile pilot --scenario qa --requests 100 --concurrency 20 --write
```

Use `--scenario ingestion` for the ingestion path. The companion script
`tests/performance/run_load.py` is an alias entry point.

## Latency targets

Targets for time to first word: p95 3s, p99 5s, p99.9 7s. A typical
question must be answered in under 15s.

| Step | Typical | Bad day (p95) |
|---|---|---|
| Request in | 90 ms | 200 ms |
| Input gate | 50 ms | 80 ms |
| Understand the question | 100-400 ms | 800 ms |
| Hybrid search | 100 ms | 200 ms |
| Rerank | 250 ms | 400 ms |
| Evidence check, router, gateway | 40 ms | 60 ms |
| Strong model first word | 900 ms | 1,650 ms |
| Output gate and first word back | 60 ms | 100 ms |

## Budgets

- First-word timing: p95 <= 3000 ms, p99 <= 5000 ms, p999 <= 7000 ms.
- Streaming behavior: first chunk p95 <= 1500 ms, total stream p95 <= 15000 ms, no more than one buffered chunk.
- Search: hybrid search p95 <= 200 ms, p99 <= 400 ms.
- Reranking: p95 <= 400 ms, p99 <= 800 ms.
- Database interactions: query p95 <= 100 ms, p99 <= 250 ms, connection wait p95 <= 50 ms.

## Concurrency caps and waiting line

- Question path: `lambda_reserved_concurrency` (pilot 20, standard 40).
- Ingestion path: `ingestion_max_concurrency` (4), strictly below the question cap.
- Database pool per function: 3 connections, with `db_connections_per_request` <= pool allowance.
- Waiting line: bounded semaphore with FIFO wait; tracks max queue depth and wait time. Max wait p95 <= 1000 ms, max queue depth <= 200.

## Concurrency caps under load

The harness inflates request counts above the cap so the waiting line
actually queues. Metrics report `waited_count` and `max_queue_depth`.

## Scheduling

Performance runs are scheduled or label-triggered (`load-test` or
`performance`) so they do not block fast PR feedback. See
`.github/workflows/performance.yml`.

## Throughput baseline

Recorded baselines include `throughput_qps` measured by the harness for
pilot and standard profiles on both Q&A and ingestion paths.
