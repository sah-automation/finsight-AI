# Domain Value Objects

Immutable objects compared by value, not identity.

**Belongs here:**
- `Money` - amount, currency, units (thousands/millions)
- `Period` - fiscal period with start/end
- `Citation` - source reference (doc, page, table, chars)
- `Confidence` - score with reasoning

**Rules:**
- Frozen Pydantic models or `@dataclass(frozen=True)`
- Money always carries currency and units
- Never pass bare numbers for financial values

**Does not belong here:**
- Entities with identity (those go in `entities/`)
- Mutable objects
- Objects with business behavior (those are entities or services)