## Parent

Part of #115

## What to build

Verify and cover the standard tracing span attributes: step, company, duration, active switch values, model name, retry count, cache hit, and queue wait. Prove redaction of question text, chunk text, answers, PII, credentials, and signed URLs. Confirm the five alert mappings (fallback 3, reranker down, embedding retries, retry-list job, stale role cache) exist in infrastructure and are snapshot- or test-covered.

## Acceptance criteria

- [ ] Standard span attributes are emitted by the shared tracing decorators.
- [ ] Sensitive fields never appear in spans or logs.
- [ ] All five alert mappings are present and covered by tests or snapshots.
- [ ] Binding pre-flight followed; gates green.
