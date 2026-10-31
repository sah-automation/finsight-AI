## Parent

Part of #115

## What to build

Split update, delete, reprocess, and onboarding orchestration into named steps. Preserve delta updates, supersession, soft delete and purge, rolling reprocess with atomic commit, onboarding idempotency, and partition readiness checks.

## Acceptance criteria

- [ ] Each flow is decomposed into named, testable steps.
- [ ] Idempotency, atomicity, retention, and state transitions are preserved.
- [ ] Switch paths remain tested.
- [ ] Existing application and integration tests pass.
- [ ] Binding pre-flight followed; gates green.
