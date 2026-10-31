## Parent

Part of #115

## What to build

Extract adapter factories and reader registries from the composition root into focused modules. The root should select and assemble; it must not contain business logic, vendor branching, or construction fallbacks. Preserve pilot/standard differences as config-only differences and fail loudly when construction fails.

## Acceptance criteria

- [ ] Adapter and registry factories live in focused modules; the composition root is materially smaller.
- [ ] Composition contains no business logic or vendor branching.
- [ ] Pilot and standard modes differ only by config.
- [ ] Construction failures propagate instead of returning a partial container.
- [ ] Composition tests cover wiring, mode selection, and loud failure.
- [ ] Binding pre-flight followed; gates green.
