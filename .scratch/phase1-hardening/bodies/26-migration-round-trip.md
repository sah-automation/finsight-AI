## Parent

Part of #115

## What to build

Exercise the migration chain against a test database: upgrade → downgrade → upgrade, including Company partitions and vector indexes. Keep the test integration-only where real services are unavailable and document the checks that must pass in staging/CI.

## Acceptance criteria

- [ ] Upgrade → downgrade → upgrade passes against the test database.
- [ ] Company partitions and vector indexes are created and recreated correctly.
- [ ] Integration-only portions are documented for staging/CI.
- [ ] Migration test is wired into the appropriate CI lane.
- [ ] Binding pre-flight followed; relevant gates green.
