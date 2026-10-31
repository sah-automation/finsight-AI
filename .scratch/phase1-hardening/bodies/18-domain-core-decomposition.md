## Parent

Part of #115

## What to build

Split the oversized domain and core modules (DocumentVersion, calculator, evidence checker, output gate, citation locator, residual config modules) into under-limit modules while preserving behavior, invariants, and dependency direction.

## Acceptance criteria

- [ ] Each module is under the documented size limits.
- [ ] Domain and core tests remain green without behavior changes.
- [ ] No vendor, config, or environment reads are introduced.
- [ ] Binding pre-flight followed; gates green.
