## Parent

Part of #115

## What to build

Add end-to-end cross-Company isolation coverage across every endpoint and data path. Prove a Company cannot read another Company's Documents, Chunks, Answers, Citations, cache entries, metering rows, traces, queue payloads, or repository rows. Deny by default.

## Acceptance criteria

- [ ] Each relevant endpoint is exercised for Company A versus Company B.
- [ ] Data paths cover Documents, Chunks, Answers, Citations, caches, metering, tracing, queue, and repositories.
- [ ] Denied access does not leak existence or content.
- [ ] Isolation tests run in the appropriate unit or integration lane.
- [ ] Binding pre-flight followed; gates green.
