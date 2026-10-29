"""Input gate - normalizes, checks and gates questions before model calls."""

from __future__ import annotations

import re
import unicodedata

from finsight.core.errors import PolicyBlocked

# ---------------------------------------------------------------------------
# PII detection helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_RE = re.compile(r'(?<!\d)(?:\+?\d[\s().-]*){7,}\d(?!\d)')
_SSN_RE = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
_CARD_RE = re.compile(r'\b(?:\d[ -]?){13,16}\b')

_INJECTION_PATTERNS = [
    r'\bignore (?:all |any |previous |prior |above )?(?:instructions|rules|prompts?)\b',
    r'\bdisregard (?:all |any |previous |prior |above )?(?:instructions|rules|prompts?)\b',
    r'\bforget (?:all |any |previous |prior |above )?(?:instructions|rules|prompts?)\b',
    r'\b(?:reveal|show|print|dump|output)\s+(?:your|the)\s+(?:system |hidden |internal )?(?:prompt|instructions|policy)\b',
    r'\byou are now\b',
    r'\bact as (?:a |an )?(?:admin|root|system|developer|jailbreak)\b',
    r'\bjailbreak\b',
    r'\bdo anything now\b',
    r'\bbypass (?:the )?(?:safety|rules|guardrails?|policy)\b',
    r'\boverride (?:the )?(?:safety|rules|guardrails?|policy)\b',
    r'\bsystem prompt\b',
]
_INJECTION_RE = re.compile('|'.join(_INJECTION_PATTERNS), re.IGNORECASE)


def _normalise_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def detect_pii(text: str) -> list[str]:
    """Return the kinds of PII detected in *text*."""
    kinds: list[str] = []
    if _EMAIL_RE.search(text):
        kinds.append('email')
    if _PHONE_RE.search(text):
        kinds.append('phone')
    if _SSN_RE.search(text):
        kinds.append('ssn')
    if _CARD_RE.search(text):
        kinds.append('credit_card')
    return kinds


def mask_pii(text: str) -> str:
    """Return a copy of *text* with detected PII replaced."""
    result = _EMAIL_RE.sub('[REDACTED_EMAIL]', text)
    result = _PHONE_RE.sub('[REDACTED_PHONE]', result)
    result = _SSN_RE.sub('[REDACTED_SSN]', result)
    return _CARD_RE.sub('[REDACTED_CARD]', result)


def detect_prompt_injection(text: str) -> bool:
    """Return True when *text* looks like a prompt-injection attempt."""
    return bool(_INJECTION_RE.search(text))


from .input_gate_result import InputGateResult


class InputGate:
    """Pure domain service that gates questions before any model call."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        max_length = kwargs.get('max_question_length')
        max_question_length = kwargs.get('max_question_characters')
        if max_length is None:
            max_length = max_question_length
        pii_action = kwargs.get('pii_action')
        pii_detection_enabled = kwargs.get('pii_detection_enabled')
        injection_enabled = kwargs.get('prompt_injection_detection_enabled')
        if injection_enabled is None:
            injection_enabled = kwargs.get('prompt_injection_enabled')
        if pii_detection_enabled is None:
            pii_detection_enabled = True
        if injection_enabled is None:
            injection_enabled = True
        if max_length is None:
            max_length = 4000

        cfg = kwargs.get('config') or kwargs.get('security_config') or kwargs.get('settings')
        if cfg is not None:
            max_length = getattr(cfg, 'max_question_length', max_length)
            pii_action = getattr(cfg, 'pii_action', pii_action)
            pii_detection_enabled = getattr(cfg, 'pii_detection_enabled', pii_detection_enabled)
            injection_enabled = getattr(cfg, 'prompt_injection_detection_enabled', injection_enabled)

        for arg in args:
            if isinstance(arg, int) and not isinstance(arg, bool):
                max_length = arg
            elif isinstance(arg, str):
                try:
                    pii_action = arg
                except Exception:  # pragma: no cover - simple assignment
                    pass
            elif hasattr(arg, 'max_question_length'):
                cfg = arg
                max_length = getattr(cfg, 'max_question_length', max_length)
                pii_action = getattr(cfg, 'pii_action', pii_action)
                pii_detection_enabled = getattr(cfg, 'pii_detection_enabled', pii_detection_enabled)
                injection_enabled = getattr(cfg, 'prompt_injection_detection_enabled', injection_enabled)

        self.max_question_length = int(max_length) if isinstance(max_length, int) else 4000
        self.pii_action = str(pii_action).lower() if pii_action is not None else 'log'
        self.pii_detection_enabled = bool(pii_detection_enabled)
        self.prompt_injection_detection_enabled = bool(injection_enabled)
        self.block_on_injection = bool(kwargs.get('block_on_injection', True))
        self.company_id = kwargs.get('company_id')

    def _normalize(self, question: object) -> str:
        text = '' if question is None else str(question)
        text = unicodedata.normalize('NFKC', text)
        return _normalise_whitespace(text)

    def check(self, question: object = None, *args: object, **kwargs: object) -> InputGateResult:
        if question is None:
            question = kwargs.get('question') or kwargs.get('text') or kwargs.get('query') or kwargs.get('input')
        original = '' if question is None else str(question)
        normalized = self._normalize(question)

        pii_kinds: list[str] = []
        if self.pii_detection_enabled:
            pii_kinds = detect_pii(normalized)

        injection = False
        if self.prompt_injection_detection_enabled:
            injection = detect_prompt_injection(normalized)

        allowed = True
        reason: str | None = None

        if len(normalized) > self.max_question_length:
            allowed = False
            reason = 'question_too_long'
        elif injection and self.block_on_injection:
            allowed = False
            reason = 'prompt_injection'
        elif pii_kinds:
            action = self.pii_action
            if action == 'block':
                allowed = False
                reason = 'pii_detected'
            elif action == 'mask':
                normalized = mask_pii(normalized)

        return InputGateResult(
            allowed=allowed,
            normalized_question=normalized,
            question=normalized,
            original_question=original,
            reason=reason,
            pii_detected=bool(pii_kinds),
            pii_kinds=pii_kinds,
            pii_action=self.pii_action,
            injection_detected=injection,
            max_length=self.max_question_length,
            company_id=self.company_id,
        )

    # Compatibility aliases
    def run(self, *args: object, **kwargs: object) -> InputGateResult:
        return self.check(*args, **kwargs)

    def validate(self, *args: object, **kwargs: object) -> InputGateResult:
        return self.check(*args, **kwargs)

    def gate(self, *args: object, **kwargs: object) -> InputGateResult:
        return self.check(*args, **kwargs)

    def process(self, *args: object, **kwargs: object) -> InputGateResult:
        return self.check(*args, **kwargs)

    def normalize(self, *args: object, **kwargs: object) -> str:
        result = self.check(*args, **kwargs)
        return result.normalized_question

    def enforce(self, *args: object, **kwargs: object) -> InputGateResult:
        result = self.check(*args, **kwargs)
        if not result.allowed:
            raise PolicyBlocked(result.reason or 'input_blocked')
        return result

    def __call__(self, *args: object, **kwargs: object) -> InputGateResult:
        return self.check(*args, **kwargs)


# Convenience functions
def input_gate(question: object = None, *args: object, **kwargs: object) -> InputGateResult:
    data = dict(kwargs)
    q = question
    if q is None:
        q = data.pop('question', None) or data.pop('text', None) or data.pop('query', None) or data.pop('input', None)
    if q is None and args:
        first = args[0]
        if not hasattr(first, 'max_question_length') and not isinstance(first, bool):
            q = first
            args = args[1:]
    gate = InputGate(*args, **data)
    return gate.check(q)


def build_input_gate(*args: object, **kwargs: object) -> InputGate:
    return InputGate(*args, **kwargs)


InputGateService = InputGate
InputGater = InputGate
QuestionInputGate = InputGate
__all__ = [
    'InputGate',
    'InputGateResult',
    'InputGateService',
    'InputGater',
    'QuestionInputGate',
    'build_input_gate',
    'detect_pii',
    'detect_prompt_injection',
    'input_gate',
    'mask_pii',
]
