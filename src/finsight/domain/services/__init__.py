"""Pure domain services."""

from .cache_key import build_answer_cache_key
from .calculator import (
    CalculateService,
    CalculationResult,
    CalculationService,
    Calculator,
    MetricCalculator,
    calculate,
)
from .citation import (
    CitationCheck,
    CitationChecker,
    CitationValidationResult,
    CitationValidator,
    check_citation,
    validate_citation,
)
from .delta_differ import DeltaDiffer
from .delta_result import DeltaResult
from .document_stamp import DocumentStamp
from .evidence import (
    EvidenceCheck,
    EvidenceChecker,
    EvidenceGate,
    EvidenceResult,
    EvidenceService,
    answer_has_evidence,
    has_sufficient_evidence,
    is_citation_valid,
)
from .input_gate import (
    InputGate,
    InputGateResult,
    detect_pii,
    detect_prompt_injection,
    mask_pii,
)
from .output_gate import (
    OutputGate,
    OutputValidator,
    OutputVerification,
    OutputVerificationResult,
    OutputVerifier,
    verify_output,
)
from .permission_policy import is_permission_allowed
from .route_decision import RouteDecision
from .router import (
    DeterministicRouter,
    ModelRouter,
    ModelSelectionRouter,
    QuestionRouter,
    Router,
    route_question,
)

__all__ = [
    'CalculateService',
    'CalculationResult',
    'CalculationService',
    'Calculator',
    'CitationCheck',
    'CitationChecker',
    'CitationValidationResult',
    'CitationValidator',
    'DeltaDiffer',
    'DeltaResult',
    'DeterministicRouter',
    'DocumentStamp',
    'EvidenceCheck',
    'EvidenceChecker',
    'EvidenceGate',
    'EvidenceResult',
    'EvidenceService',
    'InputGate',
    'InputGateResult',
    'MetricCalculator',
    'ModelRouter',
    'ModelSelectionRouter',
    'OutputGate',
    'OutputValidator',
    'OutputVerification',
    'OutputVerificationResult',
    'OutputVerifier',
    'QuestionRouter',
    'RouteDecision',
    'Router',
    'answer_has_evidence',
    'build_answer_cache_key',
    'calculate',
    'check_citation',
    'detect_pii',
    'detect_prompt_injection',
    'has_sufficient_evidence',
    'is_citation_valid',
    'is_permission_allowed',
    'mask_pii',
    'route_question',
    'validate_citation',
    'verify_output',
]
