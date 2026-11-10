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

**Gemini 3+ model family (issue #262):**

For Gemini 3+ model ids (detected from the resolved model id of each chain
entry by `_llm_gateway_gemini.py`, e.g. `gemini-3.8-flash` or
`gemini-3.6-flash`), the gateway omits the deprecated
`temperature`/`top_p`/`top_k` parameters from the provider call — LiteLLM
warns they are "planned for removal; move sampling guidance into the system
instructions instead" — and appends determinism wording ("answer
deterministically … no sampling variety") to the system message. Non-Gemini
families (groq, nvidia_nim, self_hosted, openai-style paths) keep receiving
the configured parameters unchanged. This is model-family correctness derived
from the configured model identity, not a config switch (issue #262 decision):
no schema change, and the switch list is unchanged.

**Behavioral tradeoff — verify, do not assume:** dropping
`temperature: 0.0` moves Gemini 3+ sampling behavior to the provider default.
The golden set gate (`make test-golden`) must run before merge; if
determinism or answer quality regresses, escalate with the golden results
rather than weakening the change (speed/compat never beats quality). Gateway
boundary unit tests live in `tests/unit/adapters/llm/test_gemini_3_sampling_params.py`.
