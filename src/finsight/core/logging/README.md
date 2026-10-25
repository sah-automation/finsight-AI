# Core Logging

Logger setup and trace tag utilities.

**Belongs here:**
- Logger configuration
- Trace context management
- Structured logging helpers
- Sensitive-field redaction (`redaction.py`)

**Does not belong here:**
- Business logic
- Application-specific log messages (those go where the logic lives)
- Direct use of `print()` or standard library logging without our wrapper
