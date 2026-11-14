## Parent

Part of #115

## What to build

Make provider, model, chain role (answer, cheap, fallback, embedding, rerank), timeout, and retry selection fully config-driven. Add a config-driven approved-model list per environment and region; validate every configured model; enforce exactly three distinct fallbacks per chain and a self-hosted in-region fallback 3; validate failover conditions and price coverage for every configured model. Reconcile dev, staging, and production profiles with decision D9 (Gemini primary and embeddings, Groq cheap, NVIDIA NIM fallback and reranker). Adding Anthropic, OpenAI, or another approved provider later must require config plus adapter registration only.

## Acceptance criteria

- [ ] All model and provider selection comes from typed config; no business or adapter-construction module hardcodes a vendor.
- [ ] The approved-model list rejects unapproved models and validates region.
- [ ] Fallback-chain rules and failover conditions are enforced.
- [ ] Missing price-table entries stop startup.
- [ ] Profiles reflect D9; a test proves a new approved model can be introduced by config.
- [ ] Binding pre-flight followed; relevant gates green.
