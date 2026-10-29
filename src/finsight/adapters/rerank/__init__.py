"""Rerank adapters (cross-encoder scoring with a safe fallback)."""

from .cohere_reranker import CohereReranker
from .rerank_result import RerankResult

__all__ = ['CohereReranker', 'RerankResult']
