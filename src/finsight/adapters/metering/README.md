# Metering Adapter

Usage tracking and cost recording.

**Implements:** `MeteringPort` (record_usage)

**Belongs here:**
- `DynamoMetering` - usage rows in DynamoDB
- Cost calculation from config/prices.yaml
- Batch writes for efficiency
- Trace ID correlation

**Decorator pattern:** `MeteredLLM`, `MeteredEmbedding`, etc. wrap adapters so no call site forgets metering

**Rule:** A paid call without a usage row is a bug

**Does not belong here:**
- Pricing config (that's config/prices.yaml)
- Billing logic (separate service)
- Alerting (that's observability)