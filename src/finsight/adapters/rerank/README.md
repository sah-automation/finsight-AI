# Rerank Adapter

Cross-encoder reranking of search results.

**Implements:** `Reranker` port

**Belongs here:**
- `CohereReranker` - via Cohere API
- `LocalReranker` - local model fallback
- Score normalization
- Batch reranking

**Config switch:** Reranker on/off (both paths tested)

**Does not belong here:**
- Initial vector search (that's vector_store/)
- Business logic about when to rerank
