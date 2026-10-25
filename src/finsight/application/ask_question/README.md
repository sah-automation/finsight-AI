# Ask Question Use Case

Question answering flow steps.

**Belongs here:**
- Input validation gate
- Query embedding
- Vector search
- Reranking
- Prompt building
- LLM generation
- Citation checking
- Output validation gate

**Flow:** Each step has interface `run(context) -> context`. Steps can be added, reordered, or run in parallel.