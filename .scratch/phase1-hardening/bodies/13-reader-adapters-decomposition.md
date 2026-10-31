## Parent

Part of #115

## What to build

Split the oversized reader adapters into under-limit modules while preserving the common reader return shape, page routing, table/layout handling, scan-reader rejection behavior, and every supported file format.

## Acceptance criteria

- [ ] Each reader module is under the documented file and function limits.
- [ ] One public reader class per file and filename matches the class.
- [ ] Reader contract and unit tests remain green.
- [ ] Reader, scan-reader, and table-reader switch paths remain covered.
- [ ] Binding pre-flight followed; gates green.
