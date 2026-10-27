# 01: Add partition metadata schema and partitioned table structure

**What to build:** Create the foundation for per-company partitions by adding a `partition_metadata` table to track partition creation, and prepare the schema for partitioning. This creates the tracking mechanism needed for migrations and upload gates without breaking existing functionality.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Add `partition_metadata` table migration (company_id, partition_name, indexes, created_at, etc.)
- [ ] Add partition metadata model/entity in domain (pure, no I/O)
- [ ] Create ports for partition metadata access
- [ ] Ensure migration is reversible (downgrade works)
