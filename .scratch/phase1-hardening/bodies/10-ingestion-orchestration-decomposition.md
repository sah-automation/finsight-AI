## Parent

Part of #115

## What to build

Split the ingestion orchestration into named steps with narrow inputs and outputs. Preserve step ordering, switch behavior, idempotency, DocumentVersion state transitions, retries/DLQ handling, delta tracking, and version supersession. Each step must be testable without running the whole pipeline.

## Acceptance criteria

- [ ] Ingestion orchestration is decomposed into named, independently testable steps.
- [ ] Step order, switch paths, idempotency, and state transitions are preserved.
- [ ] Delta tracking, versioning, and retry/DLQ behavior remain covered.
- [ ] Existing ingestion and golden-fixture tests pass.
- [ ] Binding pre-flight followed; gates green.
