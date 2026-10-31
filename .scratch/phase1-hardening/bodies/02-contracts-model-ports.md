## Parent

Part of #115

## What to build

Add shared contract suites for `LLMGateway` and `EmbeddingProvider` under the existing contract-test pattern. Run each suite against every concrete adapter and test double. Cover happy path, provider failure/timeout, empty or invalid input, company scoping, and compatibility with the metering/tracing decorator stacks.

## Acceptance criteria

- [ ] Shared suites exist for both ports and run against every concrete adapter.
- [ ] The contract matrix and README list both ports and their adapters.
- [ ] The architecture contract-matrix meta-test covers both ports.
- [ ] Tests assert external behavior, not private implementation.
- [ ] Binding pre-flight followed; relevant gates are green.
