# 02: Add PartitionManager and repository ports for tenancy

**What to build:** Define the domain interfaces (ports) for partition management and ensure repository ports require `company_id` on all tenant data access methods per coding standards. These are pure interfaces with no implementation.

**Blocked by:** 01: Add partition metadata schema and partitioned table structure

**Status:** ready-for-agent

- [ ] Add `domain/ports/partition_manager.py` with create_partition, ensure_partition_exists, drop_partition, list_partitions, record_partition_metadata
- [ ] Add `domain/ports/partition_metadata_repository.py`
- [ ] Update existing repository ports to require company_id where applicable (or create base patterns)
- [ ] Add any needed domain entities/value objects for partition metadata
