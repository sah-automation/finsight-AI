# 04: Implement PartitionManager adapter

**What to build:** Create the concrete implementation of PartitionManager that can create partitions, indexes, vector indexes per company. It must be idempotent and record partition metadata. This is the first adapter that actually does the partition creation.

**Blocked by:** 03: Convert core tables to partitioned structure with RLS

**Status:** ready-for-agent

- [ ] Create `src/finsight/adapters/partitions/partition_manager.py`
- [ ] Implement create_partition to create partition, indexes, and vector indexes
- [ ] Implement ensure_partition_exists (idempotent check)
- [ ] Record partition metadata on creation
- [ ] Handle errors clearly
