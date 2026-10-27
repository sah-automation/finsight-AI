# 07: Add onboarding API endpoint with System Admin authz

**What to build:** Create the onboarding endpoint that only System Admin can call. Accept request_key, validate inputs, return status (setting-up/ready), and mark ready only after final commit. Must enforce authorization.

**Blocked by:** 06: Create onboarding application use case

**Status:** ready-for-agent

- [ ] Create `src/finsight/entrypoints/api/onboarding.py`
- [ ] Enforce System Admin role check
- [ ] Accept request_key for idempotency
- [ ] Validate inputs before submit
- [ ] Return clear non-leaking errors
- [ ] Wire to onboarding use case
