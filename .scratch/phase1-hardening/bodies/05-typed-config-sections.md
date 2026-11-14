## Parent

Part of #115

## What to build

Replace arbitrary extended config fields with typed, frozen models for database, traffic, protection, encryption, lambda, models, cache, edge, scale, answer_check, metering, consistency, and access. Remove the `*_ext` duplication so each section has one typed owner. Split the config model module into focused per-section modules while preserving the public config surface and unknown-key rejection.

## Acceptance criteria

- [ ] No `Any`-typed extended config section remains.
- [ ] Every section is frozen and validated; unknown keys still fail loudly.
- [ ] Config models are split under the documented file-size limit and imports are updated.
- [ ] All environment profiles load under `make config-check`.
- [ ] Tests cover each new section and its defaults.
- [ ] Binding pre-flight followed; architecture and unit gates green.
