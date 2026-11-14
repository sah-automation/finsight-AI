## Parent

Part of #115

## What to build

Add shared contract suites for `ObjectStorage`, `QueuePort`, and `PartitionGateway`, and add the missing concrete `UnitOfWork` adapter over the existing database session plus its shared contract suite. Wire the new adapter in the composition root. Cover errors, idempotency, company scoping, commit/rollback, and failure paths.

## Acceptance criteria

- [ ] Shared suites exist for ObjectStorage, QueuePort, PartitionGateway, and UnitOfWork.
- [ ] A concrete UnitOfWork adapter implements the port, is wired in composition, and commits/rolls back correctly.
- [ ] The contract matrix and README list all four ports.
- [ ] Failure and idempotency paths are covered.
- [ ] Binding pre-flight followed; relevant gates green.
