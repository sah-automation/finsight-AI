"""Input gate - normalizes, checks and gates questions before model calls."""

from __future__ import annotations

import re
import unicodedata

from finsight.core.errors import PolicyBlocked

from .input_gate_result import InputGateResult

# ---------------------------------------------------------------------------
# PII detection helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_RE = re.compile(r'(?<!\d)(?:\+?\d[\s().-]*){7,}\d(?!\d)')
_SSN_RE = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
_CARD_RE = re.compile(r'\b(?:\d[ -]?){13,16}\b')

_INVISIBLE_RE = re.compile(r'[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u180e\u200c\u200d]+')

_INJECTION_PATTERNS = [
    r'\bignore (?:all |any |previous |prior |above )*(?:instructions|rules|prompts?)\b',
    r'\bdisregard (?:all |any |previous |prior |above )*(?:instructions|rules|prompts?)\b',
    r'\bforget (?:all |any |previous |prior |above )*(?:instructions|rules|prompts?)\b',
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
    folded = unicodedata.normalize('NFKC', '' if text is None else str(text))
    folded = _INVISIBLE_RE.sub('', folded)
    folded = _normalise_whitespace(folded)
    return bool(_INJECTION_RE.search(folded))


def _unfold_config(value: object) -> object:
    """Unwrap a full Config (or dict) to its security section when present."""
    if value is None:
        return None
    if isinstance(value, dict):
        nested = value.get('security')
        return nested if nested is not None else value
    nested = getattr(value, 'security', None)
    return nested if nested is not None else value


def _config_like(value: object) -> bool:
    if value is None:
        return False
    return not isinstance(value, (str, bytes, int, float, bool))


def _cfg_get(config: object, name: str, default: object = None) -> object:
    if config is None:
        return default
    if isinstance(config, dict):
        if name in config:
            value = config.get(name, default)
            return default if value is None else value
        return default
    sentinel = object()
    value = getattr(config, name, sentinel)
    if value is sentinel or value is None:
        return default
    return value


class InputGate:
    """Pure domain service that gates questions before any model call."""

    def __init__(
        self, config: object = None, *, company_id: object = None, block_on_injection: bool = True
    ) -> None:
        if not _config_like(config):
            raise TypeError(
                'InputGate requires a typed configuration dependency (config=SecurityConfig or Config).'
            )

        resolved = _unfold_config(config)

        max_length_raw = _cfg_get(resolved, 'max_question_length', None)
        if (
            isinstance(max_length_raw, int)
            and not isinstance(max_length_raw, bool)
            and max_length_raw >= 1
        ):
            self.max_question_length = max_length_raw
        else:
            self.max_question_length = 4000

        pii_action_raw = _cfg_get(resolved, 'pii_action', None)
        self.pii_action = str(pii_action_raw).lower() if pii_action_raw is not None else 'log'

        pii_detection_raw = _cfg_get(resolved, 'pii_detection_enabled', None)
        self.pii_detection_enabled = True if pii_detection_raw is None else bool(pii_detection_raw)

        injection_raw = _cfg_get(resolved, 'prompt_injection_detection_enabled', None)
        self.prompt_injection_detection_enabled = (
            True if injection_raw is None else bool(injection_raw)
        )

        self.block_on_injection = bool(block_on_injection)
        self.company_id = (
            company_id if company_id is not None else _cfg_get(resolved, 'company_id', None)
        )

    def _normalize(self, question: object) -> str:
        text = '' if question is None else str(question)
        text = unicodedata.normalize('NFKC', text)
        text = _INVISIBLE_RE.sub('', text)
        return _normalise_whitespace(text)

    def check(
        self,
        question: object = None,
        *,
        company_id: object = None,
    ) -> InputGateResult:
        return self._check_impl(question, company_id=company_id)

    def _check_impl(
        self,
        question: object = None,
        *,
        company_id: object = None,
    ) -> InputGateResult:
        if company_id is None:
            company_id = self.company_id

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
            company_id=company_id,
        )

    def enforce(
        self,
        question: object = None,
        *,
        company_id: object = None,
    ) -> InputGateResult:
        result = self.check(question, company_id=company_id)
        if not result.allowed:
            raise PolicyBlocked(result.reason or 'input_blocked')
        return result

    def __call__(
        self,
        question: object = None,
        *,
        company_id: object = None,
    ) -> InputGateResult:
        return self.check(question, company_id=company_id)


__all__ = ['InputGate', 'InputGateResult', 'detect_pii', 'detect_prompt_injection', 'mask_pii']
