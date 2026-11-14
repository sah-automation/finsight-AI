# 06: Create onboarding application use case

**What to build:** Implement the complete onboarding orchestrator that creates a company, allocates company_id, validates region, creates partitions via PartitionManager, initializes identity/cache/audit, and marks company as ready only on final commit. Only System Admin can trigger it (enforced at entrypoint). Idempotent via request_key.

**Blocked by:** 05: Update repositories to enforce RLS context and company_id

**Status:** ready-for-agent

- [ ] Create `src/finsight/application/onboarding/` with create_company.py, models.py, __init__.py
- [ ] Validate inputs (region, email), allocate company_id
- [ ] Resolve region/cell via config
- [ ] Create company record (starts incomplete), create partition, indexes, vector indexes
- [ ] Transaction safe - ready only on final commit
- [ ] Idempotent via request_key
- [ ] Write audit log, record partition metadata
- [ ] Initialize role cache/stamp as needed
