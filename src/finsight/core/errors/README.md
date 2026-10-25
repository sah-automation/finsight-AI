# Core Errors

Custom error types grouped by meaning.

**Belongs here:**
- `UserFacingError` - errors safe to show to users
- `RetryableError` - errors that warrant a retry
- `PolicyBlocked` - blocked by policy (e.g., permissions)
- `InsufficientData` - normal result when data is lacking

**Does not belong here:**
- Raw exception handling
- Vendor-specific error wrapping (do that in adapters)
- Business rule validation (that's in domain/services)