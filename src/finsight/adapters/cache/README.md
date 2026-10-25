# Cache Adapter

DynamoDB caches for answers and roles.

**Implements:** `CachePort` (get, set, delete, exists with TTL)

**Belongs here:**
- `DynamoAnswerCache` - key: company+role+scope+question+doc_stamp
- `DynamoRoleCache` - permissions cache
- TTL management
- Conditional writes for consistency

**Test requirement:** Unit test proves answer cache key includes all required components

**Does not belong here:**
- Cache invalidation logic (that's application/ via events)
- Business logic about what to cache
