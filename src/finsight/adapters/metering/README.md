# Metering Adapter

Usage tracking and cost recording.

**Implements:** `MeteringPort` (record_usage)

**Belongs here:**
- `DynamoMetering` - usage rows in DynamoDB
- Cost calculation from config/prices.yaml
- Batch writes for efficiency
- Trace ID correlation

`DynamoMetering` writes one row per company/trace/service/model. The sort key
is a deterministic digest of those four fields, so a retry overwrites the same
row. Numbers are stored as string-encoded decimals. Prices come from the
injected `PriceTable` (loaded from `config/prices.yaml`) and are never
hard-coded. Any write failure is logged and swallowed so metering can never fail
the user's request.

**Decorator pattern:** `MeteredLLM`, `MeteredEmbedding`, etc. wrap adapters so no call site forgets metering

**Rule:** A paid call without a usage row is a bug

**Does not belong here:**
- Pricing config (that's config/prices.yaml)
- Billing logic (separate service)
- Alerting (that's observability)
