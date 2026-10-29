"""Output verification for generated answers (pure domain)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from finsight.domain.services.input_gate import detect_pii

from .output_verification_result import OutputVerificationResult

_NUMBER_RE = re.compile(r'(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)(?!\d)')


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    text = str(value).strip()
    # strip currency/unit-ish suffixes
    text = text.replace(',', '')
    # keep digits, dot, minus
    cleaned = re.sub(r'[^0-9.\-]', '', text)
    if not cleaned or cleaned in {'.', '-', '-.'}:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _extract_numbers(text: str) -> list[Decimal]:
    if not text:
        return []
    # Ignore citation markers such as [1] when extracting numbers.
    text_for_numbers = re.sub(r'\[[^\]]*\]', ' ', text)
    nums: list[Decimal] = []
    for match in _NUMBER_RE.finditer(text_for_numbers):
        token = match.group(1).replace(',', '')
        try:
            nums.append(Decimal(token))
        except (InvalidOperation, ValueError):
            continue
    return nums


def _value_from_metric(metric: object) -> object:
    for attr in ('value', 'amount', 'figure', 'metric_value', 'result'):
        v = getattr(metric, attr, None) if not isinstance(metric, dict) else metric.get(attr)
        if v is not None:
            return v
    if isinstance(metric, dict):
        for k in ('value', 'amount', 'figure'):
            if k in metric:
                return metric[k]
    return metric


def _collect_citations(*args: object, **kwargs: object) -> list[object]:
    result: list[object] = []
    for key in ('citation', 'citations', 'sources', 'source'):
        val = kwargs.get(key)
        if val is None:
            continue
        if isinstance(val, (list, tuple, set)):
            result.extend(list(val))
        else:
            result.append(val)
    for arg in args:
        if isinstance(arg, (list, tuple, set)):
            # Could be citations if elements have document_id
            arg_seq = list(arg)
            if len(arg_seq) > 0 and hasattr(arg_seq[0], 'document_id'):
                result.extend(list(arg))
        elif arg is not None and hasattr(arg, 'document_id'):
            result.append(arg)
    # Remove None
    return [c for c in result if c is not None]


def _normalize_text(value: object) -> str:
    if value is None:
        return ''
    return str(value)


class OutputGate:
    """Pure output verification service."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.mode = (
            kwargs.get('mode')
            or kwargs.get('output_check_mode')
            or kwargs.get('timing')
            or kwargs.get('timing_mode')
            or 'per_sentence'
        )
        self.mode = 'per_sentence' if str(self.mode).lower().startswith('per') else 'full_answer'
        self.pii_action = str(kwargs.get('pii_action', 'block')).lower()
        self.pii_detection_enabled = bool(kwargs.get('pii_detection_enabled', True))
        self.number_check_enabled = bool(kwargs.get('number_check_enabled', True))
        self.block_on_failure = bool(kwargs.get('block_on_failure', True))

        cfg = kwargs.get('config') or kwargs.get('settings') or kwargs.get('output_gate_config')
        if cfg is not None:
            self.mode = getattr(cfg, 'mode', self.mode)
            if isinstance(self.mode, str):
                self.mode = 'per_sentence' if self.mode.lower().startswith('per') else 'full_answer'
            self.number_check_enabled = getattr(
                cfg, 'number_check_enabled', self.number_check_enabled
            )
            self.block_on_failure = getattr(cfg, 'block_on_failure', self.block_on_failure)

    def _allowed_numbers(
        self,
        calculated_results: object,
        cited_chunk_numbers: object,
        extra: object,
    ) -> set[Decimal]:
        allowed: set[Decimal] = set()
        # calculated results can be metrics/values/dicts
        candidates = []
        if calculated_results is not None:
            if isinstance(calculated_results, (list, tuple, set)):
                candidates.extend(list(calculated_results))
            else:
                candidates.append(calculated_results)
        if cited_chunk_numbers is not None:
            if isinstance(cited_chunk_numbers, (list, tuple, set)):
                candidates.extend(list(cited_chunk_numbers))
            else:
                candidates.append(cited_chunk_numbers)
        if extra is not None:
            if isinstance(extra, (list, tuple, set)):
                candidates.extend(list(extra))
            else:
                candidates.append(extra)
        for item in candidates:
            if hasattr(item, 'value') and not isinstance(item, (str, int, float, Decimal)):
                val = _to_decimal(item.value)
                if val is not None:
                    allowed.add(val)
                    continue
            if isinstance(item, dict):
                for key in ('value', 'amount', 'figure', 'number', 'result'):
                    if key in item:
                        val = _to_decimal(item[key])
                        if val is not None:
                            allowed.add(val)
                        break
                else:
                    # maybe dict of numbers
                    for v in item.values():
                        val = _to_decimal(v)
                        if val is not None:
                            allowed.add(val)
                continue
            val = _to_decimal(item)
            if val is not None:
                allowed.add(val)
        return allowed

    def check(
        self,
        *args: object,
        **kwargs: object,
    ) -> OutputVerificationResult:
        text = kwargs.get('text')
        if text is None:
            text = kwargs.get('answer')
        if text is None:
            text = kwargs.get('sentence')
        if text is None:
            text = kwargs.get('content')
        if text is None:
            text = kwargs.get('output')
        if text is None and args:
            # first string-like or first positional
            first = args[0]
            if isinstance(first, str):
                text = first
                args = args[1:]
        if text is None:
            text = ''
        text = _normalize_text(text)

        mode = kwargs.get('mode') or kwargs.get('timing') or kwargs.get('timing_mode') or self.mode
        if isinstance(mode, str):
            mode = 'per_sentence' if mode.lower().startswith('per') else 'full_answer'

        # citations
        citations = _collect_citations(*args, **kwargs)
        citation_ok = len(citations) > 0
        # If citations list passed alongside, check validity lazily (presence only here)
        # Actually require each citation valid-ish
        try:
            from finsight.domain.services.evidence import is_citation_valid

            if citations:
                citation_ok = all(is_citation_valid(c) for c in citations)
                if not citations:
                    citation_ok = False
        except Exception:
            pass
        if not citations:
            citation_ok = False

        # PII
        pii_kinds: list[str] = []
        if self.pii_detection_enabled:
            pii_kinds = detect_pii(text)
        pii_ok = not pii_kinds

        # numbers
        numbers_ok = True
        mismatched: list[Decimal] = []
        allowed_numbers: set[Decimal] = set()
        if self.number_check_enabled:
            calculated_results = kwargs.get('calculated_results')
            if calculated_results is None:
                calculated_results = kwargs.get('calculated')
            if calculated_results is None:
                calculated_results = kwargs.get('results')
            if calculated_results is None:
                calculated_results = kwargs.get('code_results')
            cited_chunk_numbers = kwargs.get('cited_chunk_numbers')
            if cited_chunk_numbers is None:
                cited_chunk_numbers = kwargs.get('chunk_numbers')
            if cited_chunk_numbers is None:
                cited_chunk_numbers = kwargs.get('cited_numbers')
            if cited_chunk_numbers is None:
                cited_chunk_numbers = kwargs.get('chunk_values')
            extra_numbers = kwargs.get('allowed_numbers')
            allowed_numbers = self._allowed_numbers(
                calculated_results, cited_chunk_numbers, extra_numbers
            )
            found_numbers = _extract_numbers(text)
            for num in found_numbers:
                if num not in allowed_numbers:
                    # Allow pure citation markers? already excluded by regex brackets.
                    # Allow simple 1-based small indices? Only if allowed.
                    mismatched.append(num)
            if mismatched:
                numbers_ok = False
            # If numbers exist in text but no allowed set provided, fail.
            if found_numbers and not allowed_numbers:
                numbers_ok = False

        reasons: list[str] = []
        if not citation_ok:
            reasons.append('missing_citation' if not citations else 'invalid_citation')
        if not numbers_ok:
            reasons.append('number_mismatch')
        if not pii_ok:
            reasons.append('pii_detected')

        passed = citation_ok and numbers_ok and pii_ok
        return OutputVerificationResult(
            passed,
            citation_ok=citation_ok,
            numbers_ok=numbers_ok,
            pii_ok=pii_ok,
            citation_present=bool(citations),
            numbers=_extract_numbers(text),
            allowed_numbers=sorted(allowed_numbers, key=str),
            mismatched_numbers=mismatched,
            pii_kinds=pii_kinds,
            mode=mode,
            reasons=reasons,
            reason=reasons[0] if reasons else None,
        )

    def verify(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)

    def validate(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)

    def check_output(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)

    def verify_output(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)

    def output_check(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)

    def check_sentence(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('mode', 'per_sentence')
        return self.check(*args, **kwargs)

    def check_answer(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('mode', 'full_answer')
        return self.check(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> OutputVerificationResult:
        return self.check(*args, **kwargs)


def verify_output(*args: object, **kwargs: object) -> OutputVerificationResult:
    checker_kwargs: dict[str, object] = {}
    data = dict(kwargs)
    for key in (
        'mode',
        'pii_action',
        'pii_detection_enabled',
        'number_check_enabled',
        'config',
        'settings',
        'output_gate_config',
        'output_check_mode',
        'timing',
        'timing_mode',
    ):
        if key in data:
            checker_kwargs[key] = data.pop(key)
    return OutputGate(**checker_kwargs).check(*args, **data)


OutputVerifier = OutputGate
OutputVerification = OutputGate
OutputValidator = OutputGate
__all__ = [
    'OutputGate',
    'OutputValidator',
    'OutputVerification',
    'OutputVerificationResult',
    'OutputVerifier',
    'verify_output',
]
