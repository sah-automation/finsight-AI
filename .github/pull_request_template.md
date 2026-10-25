## Summary

<!-- What changed and why. Link the issue or spec. -->

Closes #

## Layers touched

<!-- Tick every layer this PR changes. -->

- [ ] `core` (config, errors, logging, types)
- [ ] `domain`
- [ ] `application`
- [ ] `adapters`
- [ ] `entrypoints`
- [ ] `composition`
- [ ] Config (`config/`)
- [ ] Infrastructure / CI / tooling
- [ ] Docs only

## Tests added

- [ ] Unit tests
- [ ] Contract tests (if a port or adapter changed)
- [ ] Switch path tests (ON and OFF)
- [ ] Architecture invariant tests
- [ ] None needed (explain why)

## Config switches

<!-- List every switch added or changed, both paths, owner, and rollback step. Write "none" if unchanged. -->

## Checklist (CODING_STANDARDS section 17)

- [ ] Domain code has no vendor imports
- [ ] New outside dependency has a port and an adapter
- [ ] No `if vendor == ...` in business code
- [ ] Choices come from config, with both paths tested
- [ ] Constructor injection, no hidden globals
- [ ] Every data call carries `company_id`
- [ ] No maths done by the model
- [ ] No raw error can reach a user
- [ ] No sensitive data in logs
- [ ] Retries, caching, metering and tracing are decorators, not copied code
- [ ] Files and functions are small and named clearly
- [ ] Tests added: unit, contract (if a port changed), and both switch paths
- [ ] Import checker passes

## Verification

<!-- Commands you ran, and the result. -->

```bash
make check
```

## Rollback

<!-- How to revert safely. Write "revert commit" for low-risk changes. -->
