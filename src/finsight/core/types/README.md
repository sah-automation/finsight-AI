# Core Types

Shared IDs, enums, and type definitions used across layers.

**Belongs here:**
- `CompanyId`, `UserId`, `DocumentId`, `JobId` etc.
- `Role`, `Category`, `DocumentStatus`, `JobStatus` enums
- Type aliases and protocols used in multiple layers

**Does not belong here:**
- Domain entities (those go in `domain/entities/`)
- Value objects with business logic (those go in `domain/value_objects/`)
- Vendor-specific types
