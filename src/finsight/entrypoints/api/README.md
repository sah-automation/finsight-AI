# API Entrypoints

FastAPI route handlers.

**Belongs here:**
- Upload document endpoint
- Document status endpoint
- Question endpoint
- Source viewer endpoint
- Health checks

**Each handler:**
1. Extracts request data
2. Gets use case from composition
3. Calls use case
4. Maps result to response DTO
5. Handles errors -> friendly messages

**Does not belong here:**
- Validation logic (use case input gate does that)
- Business logic
- Direct repository or adapter calls
