# 10: Add tests for partitioning, RLS, and onboarding

**What to build:** Add comprehensive tests covering partition existence gate, cross-company isolation, RLS enforcement (query without setting returns nothing), idempotency, authz (only System Admin), and migration up/down.

**Blocked by:** 09: Wire everything in composition root

**Status:** ready-for-agent

- [ ] Partition tests: onboarding before upload works, partition missing blocks upload
- [ ] Security tests: company filter on every repo/query, cross-company isolation
- [ ] RLS tests: query without setting app.company_id returns nothing (fail closed)
- [ ] Migration tests: upgrade head -> downgrade base -> upgrade head with partitions
- [ ] Idempotency test: retry with same request_key returns same company
- [ ] AuthZ test: non-System Admin cannot trigger onboarding
