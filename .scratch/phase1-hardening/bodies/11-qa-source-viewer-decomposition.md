## Parent

Part of #115

## What to build

Split the Q&A and source-viewer orchestration into named steps with narrow inputs and outputs. Preserve input-gate ordering, cache and waiting-line behavior, retrieval/rerank/calculation/evidence/generation/output-gate/streaming order, citation locator minting, source authorization/fetch, and non-leaking unavailable/denied responses.

## Acceptance criteria

- [ ] Ask and source-viewer flows are decomposed into named, testable steps.
- [ ] Gate ordering, switch paths, citation behavior, and streaming remain unchanged.
- [ ] Source-viewer authorization covers allowed, denied, missing, removed, and newer-version cases.
- [ ] No sensitive text enters logs or traces.
- [ ] Binding pre-flight followed; gates green.
