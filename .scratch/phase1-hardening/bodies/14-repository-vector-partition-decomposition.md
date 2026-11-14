## Parent

Part of #115

## What to build

Split the oversized repository, Aurora vector-store, and partition adapters into under-limit modules while preserving company scoping/RLS, transaction handling, lifecycle queries, vector search/write behavior, and partition operations.

## Acceptance criteria

- [ ] Each module is under the documented size limits.
- [ ] Repository and vector contract suites pass unchanged.
- [ ] Company isolation and transaction behavior remain tested.
- [ ] Binding pre-flight followed; gates green.
