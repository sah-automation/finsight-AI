## Parent

Part of #115

## What to build

Add shared contract suites for `CompanyRepository`, `UserRepository`, `JobRepository`, and `DocumentTableRepository`, and add the missing concrete `AuditLog` adapter plus its shared contract suite. Wire the new adapter. Cover company scoping, isolation, lifecycle transitions, not-found/conflict, and idempotency.

## Acceptance criteria

- [ ] Shared suites exist for CompanyRepository, UserRepository, JobRepository, DocumentTableRepository, and AuditLog.
- [ ] A concrete AuditLog adapter implements the port, is wired, and passes the contract.
- [ ] The contract matrix and README list all five ports.
- [ ] Company isolation and not-found/conflict paths are covered.
- [ ] Binding pre-flight followed; relevant gates green.
