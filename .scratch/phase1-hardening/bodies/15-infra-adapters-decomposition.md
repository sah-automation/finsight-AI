## Parent

Part of #115

## What to build

Split the oversized S3 storage, SQS queue, answer/job-progress cache, virus-scanner, and tracing adapters while preserving idempotency, retries/DLQ, cache-key company isolation, redaction, and span behavior.

## Acceptance criteria

- [ ] Each module is under the documented size limits.
- [ ] Storage, queue, cache, scanner, and tracing behavior remains covered.
- [ ] Cache keys and traces cannot leak another Company's data.
- [ ] Binding pre-flight followed; gates green.
