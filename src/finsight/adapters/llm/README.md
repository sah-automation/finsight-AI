# LLM Adapter

LiteLLM gateway, router, and fallbacks.

**Implements:** `LLMGateway` port

**Belongs here:**
- `LiteLLMGateway` - primary implementation
- Model routing logic
- Fallback chain (models 1, 2, 3 from config)
- Token counting
- Streaming support

**Decorators (stacked from config):**
- `MeteredLLM` - records usage
- `RetryingLLM` - retry with backoff
- `CachedLLM` - prompt/response cache

**Does not belong here:**
- Prompt building (that's `application/ask_question/`)
- Business logic about when to use which model
