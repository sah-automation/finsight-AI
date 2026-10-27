# 03: Convert core tables to partitioned structure with RLS

**What to build:** Create a migration that converts shared tables (documents, document_chunks, metrics, etc.) to be partitioned BY LIST (company_id) with RLS enabled and FORCE ROW LEVEL SECURITY. Add indexes per partitioning strategy. Both locks (partition pruning + RLS) must be enforced.

**Blocked by:** 02: Add PartitionManager and repository ports for tenancy

**Status:** ready-for-agent

- [ ] Create migration to convert tables to partitioned BY LIST (company_id)
- [ ] Enable RLS on parent tables with policy `USING (company_id = current_setting('app.company_id')::uuid)`
- [ ] Add FORCE ROW LEVEL SECURITY
- [ ] Add company_id indexes first on tenant tables
- [ ] Create HNSW vector index structure per partition approach
- [ ] Ensure migration upgrade/downgrade works end-to-end
