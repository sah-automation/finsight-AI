# Embedding Adapter

Text embedding generation.

**Implements:** `EmbeddingGateway` port (part of `LLMGateway` or separate)

**Belongs here:**
- `LiteLLMEmbedding` - via LiteLLM
- Batch embedding
- Dimension validation
- Model selection from config

**Does not belong here:**
- Chunking logic (domain/services)
- Vector storage (that's vector_store/)