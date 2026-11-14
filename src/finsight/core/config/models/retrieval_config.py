from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class RetrievalConfig(StrictBaseModel):
    reranker: str = 'cross_encoder'
    hybrid_search_enabled: bool = True
    vector_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    keyword_weight: float = Field(ge=0.0, le=1.0, default=0.3)
    top_k: int = Field(ge=1, default=50)
    rerank_top_n: int = Field(ge=10, le=100, default=20)
    rerank_parallel_batches: int = Field(ge=1, default=2)
    evidence_min_score: float = Field(ge=0.0, le=1.0, default=0.30)
    evidence_min_search_score: float = Field(ge=0.0, le=1.0, default=0.50)
    evidence_min_chunks: int = Field(ge=1, default=1)

    @model_validator(mode='after')
    def validate_reranker(self) -> 'RetrievalConfig':
        if self.reranker != 'cross_encoder':
            raise ValueError('retrieval.reranker must be cross_encoder')
        return self

    @model_validator(mode='after')
    def validate_scores(self) -> 'RetrievalConfig':
        if self.evidence_min_search_score < self.evidence_min_score:
            raise ValueError('evidence_min_search_score must be >= evidence_min_score')
        if self.rerank_top_n % self.rerank_parallel_batches != 0:
            raise ValueError(
                'rerank_parallel_batches must divide rerank_top_n so each chunk is scored once'
            )
        return self
