# Scheduled Entrypoints

Cron/EventBridge triggered jobs.

**Belongs here:**
- Weekly report generator
- Forecast refresh scheduler
- Risk alert evaluator
- Cache warming jobs
- Stale data cleanup

**Each handler:**
1. Gets use case from composition
2. Calls use case for each company/tenant
3. Handles errors per-company (don't fail all)
4. Emits metrics

**Does not belong here:**
- Business logic
- Direct database queries
- Config reading