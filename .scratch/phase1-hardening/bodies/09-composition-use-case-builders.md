## Parent

Part of #115

## What to build

Extract repository, queue, storage, partition, and unit-of-work factories plus use-case builders from the composition root. Entrypoints should receive already-wired ask, source-viewer, upload, onboarding, documents, and reprocess use cases instead of rebuilding dependencies.

## Acceptance criteria

- [ ] Infrastructure factories and use-case builders are focused modules; the root is assembly only.
- [ ] Each use case is resolved once and reused by entrypoints.
- [ ] No business logic or vendor branching remains in composition.
- [ ] Composition tests cover builder output and reuse.
- [ ] Binding pre-flight followed; gates green.
