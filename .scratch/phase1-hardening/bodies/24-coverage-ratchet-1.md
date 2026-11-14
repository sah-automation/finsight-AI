## Parent

Part of #115

## What to build

Add targeted behavioral tests for the lowest-covered config, InputGate, and ingestion paths, then raise the enforced global coverage floor from 24 to 50 in one reviewed step. Coverage is a floor; tests must assert behavior, not just execute lines.

## Acceptance criteria

- [ ] Targeted tests cover config validation, InputGate behavior, and ingestion steps.
- [ ] The global coverage floor is raised to 50 in `pyproject.toml` and `Makefile`.
- [ ] The quality-standards document records the ratchet.
- [ ] Coverage gate passes without exclusions that hide adapters.
- [ ] Binding pre-flight followed; gates green.
