# Auth Adapter

Cognito authentication and authorization.

**Implements:** `AuthPort` (verify_token, get_role, get_permissions)

**Belongs here:**
- `CognitoAuth` - token verification
- JWKS caching
- Role/claim extraction
- Token refresh handling

**Does not belong here:**
- Permission definitions (those are in config/permissions.yaml)
- Business logic about access control (that's domain/services/ via Specification pattern)
- API key management (separate if needed)