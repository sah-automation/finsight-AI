# 05: Update repositories to enforce RLS context and company_id

**What to build:** Create/update repository adapters to set RLS context via `app.company_id` from RequestContext in each transaction. Ensure all repository methods require and use company_id. This enforces the second lock (RLS).

**Blocked by:** 04: Implement PartitionManager adapter

**Status:** ready-for-agent

- [ ] Create base repository pattern or update existing repos to set `SET LOCAL app.company_id = ...`
- [ ] Add `src/finsight/adapters/repositories/company_repository.py`
- [ ] Add `src/finsight/adapters/repositories/user_repository.py`
- [ ] Add `src/finsight/adapters/repositories/partition_metadata_repository.py`
- [ ] All methods must require company_id where touching tenant data
