# Research Report: Neon/Postgres Limits and KPI Time-Series Storage

**Issue:** #348 — Research Neon/Postgres limits and KPI time-series storage
**Date:** 2026-11-18
**Branch:** `research/neon-kpi-timeseries`

---

## Executive Summary

This report investigates the practical limits and patterns for materializing KPI time-series data in Neon (serverless PostgreSQL) at Phase 2 scale. Key findings:

- **Neon Free Plan (2026-11):** 1 GB storage/project (20 GB/account), 100 CU-hours/month, 2 CU max (~8 GB RAM), 5 GB network transfer/month, scale-to-zero after 5 min idle
- **Estimated Data Volume:** ~2.16M rows (5000 companies × 10 KPIs × 12 months × 3 years) at monthly granularity; ~65M rows at daily granularity
- **Storage Estimate:** ~150-300 MB for monthly data (well within 1 GB), ~4-8 GB for daily (exceeds free tier)
- **Recommended Strategy:** Native PostgreSQL partitioning by period (monthly) with `pg_partman`, covering indexes on `(company_id, kpi_code, period)`, `ON CONFLICT` upsert for incremental recomputation
- **pgvector Coexistence:** Yes, fully supported in same Neon project; separate indexes, shared compute
- **Connection Pooling:** PgBouncer in transaction mode (port 6432), 10,000 max client connections, works with existing `vector_store` switch
- **Migration Path:** Aurora Serverless v2 behind existing config switch; key differences in scale-to-zero, pricing model, and ACU vs CU units

---

## 1. Neon Free Plan Limits (As of 2026-11)

### Official Limits (per Neon Docs)

| Resource | Free Plan Limit | Notes |
|----------|-----------------|-------|
| **Postgres Storage** | 1 GB per project (20 GB total across account) | Increased from 0.5 GB in Oct 2026 |
| **Compute** | 100 CU-hours/month per project | No overage on Free — compute suspends when exhausted |
| **Max Compute Size** | 2 CU (≈8 GB RAM) | Autoscaling up to this limit |
| **Network Transfer** | 5 GB/month per project (public) | Launch/Scale: 500 GB included |
| **Scale-to-Zero** | After 5 minutes idle | Cannot be disabled on Free |
| **Branches** | 10 per project | $1.50/branch-month beyond limit |
| **Point-in-Time Recovery** | 6 hours (up to 1 GB changes) | Manual snapshots: 1 included |
| **Projects** | Up to 100 | |
| **Monitoring** | 1 day history | |
| **Managed Better Auth** | 60,000 MAU/project | |

### Compute Unit (CU) Definition
- 1 CU ≈ 4 GB memory with matching CPU
- CU-hours = CUs × hours active
- Example: 0.25 CU for 4 hours = 1 CU-hour

### What Happens When Limits Are Exceeded
- **CU-hours exhausted:** Compute suspended until next billing period or upgrade
- **Storage > 1 GB/project or 20 GB/account:** INSERT/UPDATE/DELETE operations fail until space freed or upgrade
- **Network > 5 GB:** Transfer blocked until next period or upgrade
- **Branches > 10:** Branch creation fails
- **No data deletion** occurs automatically

---

## 2. Estimated Row Count & Storage Analysis

### Monthly Granularity (Baseline)
```
5000 companies × 10 KPIs × 12 months × 3 years = 1,800,000 rows
+ 10% buffer for additional KPIs/history = ~2.0M rows
```

### Daily Granularity (If Needed)
```
5000 companies × 10 KPIs × 365 days × 3 years = 54,750,000 rows
+ buffer = ~60M rows
```

### Row Size Estimate
```sql
CREATE TABLE kpi_timeseries (
    company_id      UUID        NOT NULL,  -- 16 bytes
    kpi_code        TEXT        NOT NULL,  -- ~10-20 bytes (e.g., "revenue", "gross_margin")
    period          DATE        NOT NULL,  -- 4 bytes
    value           NUMERIC(18,4),         -- ~10 bytes
    source_doc_id   UUID,                  -- 16 bytes (nullable)
    computed_at     TIMESTAMPTZ NOT NULL,  -- 8 bytes
    PRIMARY KEY (company_id, kpi_code, period)
);
```
**Estimated row size:** ~70-90 bytes (including tuple overhead, indexes not counted)

### Storage Projection

| Granularity | Rows | Table Size | Indexes (2-3x) | Total | Free Tier Fit |
|-------------|------|------------|----------------|-------|---------------|
| Monthly | 2.0M | ~160 MB | ~320-480 MB | **~480-640 MB** | ✅ Yes (within 1 GB) |
| Daily | 60M | ~4.8 GB | ~9.6-14.4 GB | **~14-19 GB** | ❌ No (exceeds 1 GB) |

**Conclusion:** Monthly granularity fits comfortably in Free tier. Daily requires paid plan or partitioning + retention.

---

## 3. Partitioning Strategy

### Recommendation: Native Range Partitioning by `period` (Monthly) with `pg_partman`

#### Why Partition by Period (Not `company_id`)
- **Partition pruning** works best when queries filter by time range (dashboard queries: "last 12 months", "YoY comparison")
- **Even distribution:** Monthly partitions naturally balance (~160K rows/month across 5000 companies)
- **Retention:** Easy `DROP PARTITION` for old data (instant, minimal WAL)
- **pg_partman** automates partition creation/maintenance

#### Hybrid Approach (Future-Proofing)
```sql
-- Subpartition by company_id hash within each monthly partition
-- Only if single partition grows > 100M rows (not expected at Phase 2)
```

### pg_partman Setup
```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS pg_partman;

-- Create parent table
CREATE TABLE kpi_timeseries (
    company_id      UUID        NOT NULL,
    kpi_code        TEXT        NOT NULL,
    period          DATE        NOT NULL,
    value           NUMERIC(18,4),
    source_doc_id   UUID,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, kpi_code, period)
) PARTITION BY RANGE (period);

-- Configure pg_partman for monthly partitions
SELECT partman.create_parent(
    p_parent_table := 'public.kpi_timeseries',
    p_control      := 'period',
    p_type         := 'native',
    p_interval     := '1 month',
    p_start_partition := '2024-01-01',  -- Adjust to earliest data
    p_premake      := 24,               -- 2 years future partitions
    p_automatic_maintenance := 'on'
);

-- Enable infinite time partitions (auto-create as needed)
UPDATE partman.part_config
SET infinite_time_partitions = true
WHERE parent_table = 'public.kpi_timeseries';

-- Optional: Retention policy (e.g., keep 5 years)
UPDATE partman.part_config
SET retention = '5 years',
    retention_keep_table = false
WHERE parent_table = 'public.kpi_timeseries';
```

### Partition Maintenance
- **Automatic:** `pg_partman` background worker (via `pg_cron`) creates new partitions, drops old
- **Manual trigger:** `CALL partman.run_maintenance('public.kpi_timeseries');`
- **Monitor:** `SELECT * FROM partman.show_partition_info('public.kpi_timeseries');`

### Alternative: Manual Partitioning (If pg_partman Unavailable)
```sql
-- Monthly partitions created via script/migration
CREATE TABLE kpi_timeseries_2024_01 PARTITION OF kpi_timeseries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- Repeat for each month...
```

---

## 4. Indexing for Dashboard Queries

### Primary Query Patterns
1. **Company KPI dashboard:** `WHERE company_id = ? AND kpi_code IN (...) AND period BETWEEN ? AND ?`
2. **Peer comparison:** `WHERE kpi_code = ? AND period = ? AND company_id IN (...)`
3. **Trend analysis:** `WHERE company_id = ? AND kpi_code = ? ORDER BY period`

### Recommended Indexes

```sql
-- 1. Primary key (automatically created, serves pattern 1 & 3)
-- PRIMARY KEY (company_id, kpi_code, period)

-- 2. Covering index for pattern 1 (dashboard: multiple KPIs, date range)
CREATE INDEX idx_kpi_company_kpi_period_cover
    ON kpi_timeseries (company_id, kpi_code, period)
    INCLUDE (value, computed_at);

-- 3. Reverse index for pattern 2 (peer comparison: KPI + period -> companies)
CREATE INDEX idx_kpi_kpi_period_company
    ON kpi_timeseries (kpi_code, period, company_id)
    INCLUDE (value);

-- 4. BRIN index on period for time-range scans on large partitions
-- (Only on parent table; Postgres 14+ supports BRIN on partitioned tables)
CREATE INDEX idx_kpi_period_brin
    ON kpi_timeseries USING BRIN (period)
    WITH (pages_per_range = 32);
```

### Index Storage Overhead
| Index | Est. Size (Monthly) | Est. Size (Daily) |
|-------|---------------------|-------------------|
| PK (company_id, kpi_code, period) | ~160 MB | ~4.8 GB |
| Covering (company_id, kpi_code, period) INCLUDE | ~200 MB | ~6 GB |
| Reverse (kpi_code, period, company_id) INCLUDE | ~180 MB | ~5.4 GB |
| BRIN (period) | ~5 MB | ~50 MB |

**Total index overhead:** ~2-3x table size (typical for PostgreSQL)

---

## 5. Upsert Pattern for Materialized Recomputation

### Use Case
When a source document (filing, transcript) is updated, recompute affected KPIs and upsert into `kpi_timeseries`.

### Recommended Pattern: `INSERT ... ON CONFLICT`

```sql
-- Single row upsert
INSERT INTO kpi_timeseries (company_id, kpi_code, period, value, source_doc_id, computed_at)
VALUES ($1, $2, $3, $4, $5, now())
ON CONFLICT (company_id, kpi_code, period)
DO UPDATE SET
    value = EXCLUDED.value,
    source_doc_id = EXCLUDED.source_doc_id,
    computed_at = EXCLUDED.computed_at;

-- Batch upsert (sorted by PK for deadlock avoidance)
INSERT INTO kpi_timeseries (company_id, kpi_code, period, value, source_doc_id, computed_at)
SELECT * FROM unnest($1::uuid[], $2::text[], $3::date[], $4::numeric[], $5::uuid[], $6::timestamptz[])
ON CONFLICT (company_id, kpi_code, period)
DO UPDATE SET
    value = EXCLUDED.value,
    source_doc_id = EXCLUDED.source_doc_id,
    computed_at = EXCLUDED.computed_at;
```

### Performance Tips
- **Batch size:** 1000-5000 rows per statement
- **Sort by PK:** `ORDER BY company_id, kpi_code, period` before batch insert to avoid deadlocks
- **Use `COPY` + staging table** for bulk backfills (see Section 6)
- **Avoid `DO NOTHING`** unless intentionally skipping conflicts

### Incremental Recomputation Trigger
```sql
-- Function to recompute KPIs for a company/period after document update
CREATE OR REPLACE FUNCTION recompute_kpis_for_doc(p_doc_id UUID)
RETURNS VOID AS $$
DECLARE
    v_company_id UUID;
    v_period DATE;
BEGIN
    -- Get company and period from document
    SELECT company_id, period INTO v_company_id, v_period
    FROM source_documents WHERE id = p_doc_id;

    -- Delete affected KPIs (cascade to upsert)
    DELETE FROM kpi_timeseries
    WHERE company_id = v_company_id AND period = v_period
      AND kpi_code IN (SELECT kpi_code FROM kpi_definitions WHERE depends_on_doc_type = ...);

    -- Recompute via application logic (not in DB function for complexity)
    -- Application calls upsert with new values
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Rebuild/Backfill Job Performance & Cost

### Scenario: Full Rebuild of 2M Rows (Monthly)

#### Approach 1: `COPY` + Staging Table (Fastest)
```sql
-- 1. Create staging table (unlogged for speed)
CREATE UNLOGGED TABLE kpi_timeseries_staging (LIKE kpi_timeseries INCLUDING ALL);

-- 2. COPY from CSV/Parquet (via application)
-- COPY kpi_timeseries_staging FROM STDIN WITH (FORMAT CSV);

-- 3. Swap partitions (minimal downtime)
-- For each partition:
--   ALTER TABLE kpi_timeseries DETACH PARTITION kpi_timeseries_2024_01;
--   ALTER TABLE kpi_timeseries_staging ATTACH PARTITION kpi_timeseries_staging_2024_01
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
--   DROP TABLE kpi_timeseries_2024_01;
--   ALTER TABLE kpi_timeseries_staging RENAME TO kpi_timeseries_2024_01;
```

#### Approach 2: Batched Upsert (Simpler, Slower)
```python
# Python pseudocode
BATCH_SIZE = 5000
for batch in chunked(rows, BATCH_SIZE):
    await db.execute(upsert_sql, batch)
    # Progress tracking, resume capability
```

### Cost Estimation (Neon Free Tier)

| Operation | CU-Hours | Network | Storage Delta | Time (est.) |
|-----------|----------|---------|---------------|-------------|
| **Full rebuild (2M rows, COPY)** | ~0.5 CU-hr | ~50 MB | +160 MB | 2-5 min |
| **Full rebuild (2M rows, batched upsert)** | ~2-3 CU-hr | ~200 MB | +160 MB | 10-20 min |
| **Incremental (10K rows/day)** | ~0.01 CU-hr | ~1 MB | +1 MB | <30 sec |
| **pg_partman maintenance (monthly)** | ~0.001 CU-hr | negligible | negligible | <10 sec |

### Free Tier Budget Check
- **Monthly allowance:** 100 CU-hours
- **Typical usage:**
  - Daily incremental: 0.3 CU-hr/month
  - Weekly full refresh: 1-2 CU-hr/month
  - pg_partman maintenance: <0.1 CU-hr/month
  - Dashboard queries: 5-10 CU-hr/month (depends on traffic)
- **Total:** ~15-20 CU-hr/month → **Well within 100 CU-hr limit**

### Scale-to-Zero Impact
- Cold start: ~0.5-2 seconds (compute wake-up)
- Mitigation: Keep compute warm via periodic ping (costs ~0.25 CU-hr/day = 7.5 CU-hr/month)
- Or accept cold start for low-traffic dashboards

---

## 7. pgvector Coexistence in Same Neon Project

### Verdict: **Yes, fully supported and recommended**

### Architecture
```
Neon Project (1 GB storage)
├── Database: finsight
│   ├── Schema: public
│   │   ├── kpi_timeseries (partitioned table)     -- ~500 MB
│   │   ├── documents (source filings)             -- ~200 MB
│   │   ├── document_embeddings (pgvector)         -- ~200 MB
│   │   └── ... other tables
│   └── Extensions: pgvector, pg_partman, pg_cron
```

### pgvector Storage Estimate
```sql
CREATE TABLE document_embeddings (
    doc_id      UUID PRIMARY KEY,
    embedding   VECTOR(1536),  -- OpenAI text-embedding-3-large
    chunk_id    INT,
    content     TEXT,
    metadata    JSONB
);
```
- **1536-dim vector:** ~6 KB (1536 × 4 bytes + overhead)
- **5000 companies × 50 docs × 10 chunks = 2.5M vectors**
- **Storage:** ~15 GB (exceeds Free tier)

### Practical Coexistence Strategy
| Approach | Storage | Free Tier Fit | Notes |
|----------|---------|---------------|-------|
| **Full embeddings in Neon** | 15+ GB | ❌ No | Requires paid plan |
| **Embeddings in Neon (subset)** | 1-2 GB | ⚠️ Tight | Only recent/high-value docs |
| **Hybrid: Neon metadata + S3 vectors** | <500 MB | ✅ Yes | Store vectors in S3, metadata + ANN index in Neon |
| **Dedicated vector DB (Pinecone, etc.)** | N/A | ✅ Yes | Separate cost, more complex |

### Recommended for Phase 2: Hybrid Approach
1. **Neon:** Store `document_embeddings` with **HNSW index** on `embedding` for recent 6 months (~500K vectors = ~3 GB)
2. **Older embeddings:** Archive to S3 + rebuild index on demand
3. **Shared compute:** Both KPI queries and vector search use same Neon compute (CU-hours shared)

### Indexing pgvector in Neon
```sql
-- HNSW index (recommended for production)
CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Build with increased maintenance_work_mem (Neon allows session-level)
SET maintenance_work_mem = '2 GB';  -- Adjust for compute size
CREATE INDEX ...;
```

### Neon-Specific pgvector Notes
- `maintenance_work_mem` scales with compute size (2 CU = ~8 GB RAM → can set up to ~4 GB)
- HNSW build time: ~2-5 min for 500K vectors on 2 CU
- IVFFLAT faster build but lower recall; HNSW preferred for production

---

## 8. Connection Pooling (PgBouncer) with `vector_store` Switch

### Neon PgBouncer Configuration (Fixed, Not User-Configurable)
```ini
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 0.9 * max_connections  -- per user/database
max_prepared_statements = 1000
query_wait_timeout = 120  -- seconds
```

### Key Behaviors
| Aspect | Behavior |
|--------|----------|
| **Pool mode** | Transaction (connections returned after each transaction) |
| **Max client connections** | 10,000 (PgBouncer limit) |
| **Actual Postgres connections** | ~90% of `max_connections` (scales with compute) |
| **Prepared statements** | Limited to 1000 per connection |
| **Session-level features** | NOT supported (SET, advisory locks, temp tables, LISTEN/NOTIFY) |

### Connection Strings
```bash
# Direct (for migrations, admin) - port 5432
postgres://user:pass@ep-xxx.region.aws.neon.tech/dbname  # pragma: allowlist secret

# Pooled (for application) - port 6432
postgres://user:pass@ep-xxx.region.aws.neon.tech/dbname?pgbouncer=true  # pragma: allowlist secret
# Or use the pooled endpoint from Neon console
```

### Interaction with `vector_store` Switch
```python
# Application config (existing pattern)
class Settings:
    vector_store: Literal["neon", "pinecone", "weaviate"] = "neon"
    database_url: str  # Pooled URL for Neon
    database_url_direct: str  # Direct URL for migrations

# When vector_store == "neon":
# - Use pooled connection (port 6432) for all queries including vector search
# - PgBouncer transaction mode works fine for:
#     * KPI time-series queries (SELECT)
#     * Vector similarity search (SELECT ... ORDER BY embedding <-> ...)
#     * Upserts (INSERT ... ON CONFLICT)
# - NOT suitable for:
#     * Long-running transactions (migrations use direct URL)
#     * LISTEN/NOTIFY (not needed for this workload)
#     * Session-level SET commands (use SET LOCAL in transaction)
```

### Vercel/Serverless Deployment
```typescript
// Vercel Fluid Compute + Neon PgBouncer (recommended)
import { Pool } from 'pg';
import { attachDatabasePool } from '@vercel/functions';

const pool = new Pool({ connectionString: process.env.DATABASE_URL_POOL });
attachDatabasePool(pool);  // Reuses connections across invocations
```

---

## 9. Migration Path: Neon → Aurora Serverless v2

### When to Migrate
| Trigger | Threshold |
|---------|-----------|
| **Storage** | > 1 GB/project or > 20 GB/account (Free) / > 500 GB (Launch) |
| **Compute** | Consistently > 100 CU-hr/month (Free) / need > 2 CU max |
| **Network** | > 5 GB/month (Free) / > 500 GB (Launch) |
| **Features** | Need read replicas, private networking, HIPAA, SLA |
| **Scale-to-zero** | Need configurable/zero cold-start (Scale plan only) |

### Aurora Serverless v2 Key Differences

| Aspect | Neon (Free/Launch) | Aurora Serverless v2 |
|--------|-------------------|---------------------|
| **Scale-to-zero** | Yes (5 min, Free/Launch) | Yes (min 0 ACU, but cold start ~15-30s) |
| **Min capacity** | 0 (suspended) | 0.5 ACU (if pause enabled) |
| **Max capacity** | 2 CU (Free) / 16 CU (Launch) | 128 ACU |
| **Compute unit** | CU (4 GB RAM) | ACU (2 GB RAM) |
| **Pricing** | $0.106/CU-hr (Launch) | ~$0.12/ACU-hr (varies by region) |
| **Storage** | $0.35/GB-mo | $0.10/GB-mo (Aurora storage) |
| **Network** | 500 GB free (Launch) | $0.01-0.09/GB (inter-AZ) |
| **Branching** | Instant, free (10/project) | Snapshot/restore (slower, costs) |
| **pgvector** | Native extension | Native extension |
| **Partitioning** | pg_partman supported | pg_partman supported |

### Migration Strategy (Behind Existing Config Switch)

```python
# config/database.py (existing pattern)
class DatabaseConfig:
    backend: Literal["neon", "aurora_serverless_v2"] = "neon"

    # Neon
    neon_pool_url: str
    neon_direct_url: str

    # Aurora
    aurora_cluster_endpoint: str
    aurora_secret_arn: str
    aurora_min_acu: float = 0.5
    aurora_max_acu: float = 4.0

# Connection factory
def get_pool(config: DatabaseConfig) -> Pool:
    if config.backend == "neon":
        return Pool(config.neon_pool_url)  # PgBouncer port 6432
    else:
        # Aurora: use RDS Data API or direct with IAM auth
        return Pool(config.aurora_cluster_endpoint)
```

### Migration Steps
1. **Provision Aurora cluster** (Serverless v2, min 0.5 ACU, max 4 ACU)
2. **Enable pgvector, pg_partman** extensions
3. **Recreate schema** (same DDL works — standard PostgreSQL)
4. **Data migration:**
   ```bash
   # Option A: pg_dump/pg_restore (small DB)
   pg_dump -h neon-host -U user dbname | pg_restore -h aurora-host -U user -d dbname

   # Option B: AWS DMS (large DB, near-zero downtime)
   # Option C: Neon branch + logical replication (if available)
   ```
5. **Verify partition alignment** (pg_partman config identical)
6. **Switch config flag** → deploy
7. **Monitor** for 1 week, then decommission Neon

### Cost Comparison at Scale (Estimated)

| Monthly Load | Neon Launch | Aurora Serverless v2 |
|--------------|-------------|---------------------|
| **2 GB storage, 1 ACU avg** | $0.35×2 + $0.106×720 = **$77** | $0.10×2 + $0.12×720 = **$86** |
| **10 GB storage, 2 ACU avg** | $0.35×10 + $0.106×1440 = **$156** | $0.10×10 + $0.12×1440 = **$174** |
| **Scale-to-zero (idle 50%)** | ~$40 | ~$45 (but 0.5 ACU min if pause) |

**Note:** Aurora storage cheaper, compute slightly more expensive. Neon wins on branching, DX, scale-to-zero granularity.

---

## 10. Recommendations Summary

### For Phase 2 (Current Scale)
1. **Stay on Neon Free** — 2M rows monthly fits in 1 GB with room to grow
2. **Partition by month** using `pg_partman` (native range partitioning)
3. **Index strategy:** PK + covering index `(company_id, kpi_code, period) INCLUDE (value, computed_at)`
4. **Upsert via `ON CONFLICT`** — batch 1000-5000 rows, sorted by PK
5. **pgvector in same project** for recent embeddings only (< 6 months); archive older to S3
6. **Use pooled connections** (port 6432) for all app queries; direct for migrations
7. **Monitor CU-hours** — expect 15-20/month, well under 100 limit

### Migration Triggers (Watch These Metrics)
```sql
-- Storage per table
SELECT pg_size_pretty(pg_total_relation_size('kpi_timeseries'));

-- CU-hours (Neon API or console)
-- Network transfer (Neon console)

-- Partition count
SELECT count(*) FROM pg_class c
JOIN pg_inherits i ON c.oid = i.inhrelid
JOIN pg_class p ON p.oid = i.inhparent
WHERE p.relname = 'kpi_timeseries';
```

### When to Flip Switch to Aurora
- Storage > 500 GB (Launch limit) or consistent > 100 CU-hr/month
- Need read replicas for read-heavy dashboard scaling
- Require private networking / VPC peering / compliance (HIPAA)
- Team prefers AWS-native, single-vendor stack

---

## Appendix: Useful Queries

### Partition Health Check
```sql
SELECT
    inhrelid::regclass AS partition,
    pg_size_pretty(pg_total_relation_size(inhrelid)) AS size,
    pg_stat_get_tuples_returned(inhrelid) AS rows_read
FROM pg_inherits
WHERE inhparent = 'kpi_timeseries'::regclass
ORDER BY inhrelid;
```

### Index Usage
```sql
SELECT
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE relname = 'kpi_timeseries'
ORDER BY idx_scan DESC;
```

### pg_partman Status
```sql
SELECT * FROM partman.show_partition_info('public.kpi_timeseries');
```

---

## References

- [Neon Plans & Pricing (Official)](https://neon.com/docs/introduction/plans)
- [Neon Connection Pooling](https://neon.com/docs/connect/connection-pooling)
- [pg_partman Documentation](https://pgpartman.readthedocs.io/)
- [PostgreSQL Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [pgvector on Neon](https://neon.com/docs/extensions/pgvector)
- [Aurora Serverless v2 Docs](https://docs.aws.amazon.com/Aurora/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Neon vs Aurora Comparison](https://www.vantage.sh/blog/neon-vs-aws-aurora-serverless-postgres-cost-scale-to-zero)
