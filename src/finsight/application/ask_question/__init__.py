"""Ask-question application package."""

from .ask_orchestrator import AskOrchestrator
from .ask_question import AskQuestion
from .ask_question_use_case import AskQuestionUseCase
from .models import AskResult, UnavailableResult

Ask = AskQuestion
AskApplication = AskQuestion
AskFlow = AskQuestion
AskHandler = AskQuestion
AskService = AskQuestion
QuestionFlow = AskQuestion
QuestionUseCase = AskQuestion
QuestionAsker = AskQuestion
QaUseCase = AskQuestion
QaOrchestrator = AskQuestion
AskQuestionOrchestrator = AskQuestion
Asker = AskQuestion
AskOrchestratorUseCase = AskQuestion

__all__ = [
    'Ask',
    'AskApplication',
    'AskFlow',
    'AskHandler',
    'AskOrchestrator',
    'AskOrchestratorUseCase',
    'AskQuestion',
    'AskQuestionOrchestrator',
    'AskQuestionUseCase',
    'AskResult',
    'AskService',
    'Asker',
    'QaOrchestrator',
    'QaUseCase',
    'QuestionAsker',
    'QuestionFlow',
    'QuestionUseCase',
    'UnavailableResult',
]
