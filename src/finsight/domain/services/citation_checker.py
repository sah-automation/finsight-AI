"""Citation shape and presence validation (pure domain)."""

from __future__ import annotations

from finsight.domain.services.evidence import is_citation_valid
from finsight.domain.value_objects import Citation


def _collect_citations(*args: object, **kwargs: object) -> list[object]:
    result: list[object] = []
    for key in ('citation', 'citations', 'source', 'sources', 'items', 'values'):
        val = kwargs.get(key)
        if val is None:
            continue
        if isinstance(val, (list, tuple, set)):
            result.extend(list(val))
        else:
            result.append(val)
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, (list, tuple, set)):
            result.extend(list(arg))
        elif isinstance(arg, Citation) or hasattr(arg, 'document_id'):
            result.append(arg)
        # dict of citations?
        elif isinstance(arg, dict):
            result.extend(list(arg.values()))
    # de-dup keep order not necessary
    return [c for c in result if c is not None]


from .citation_validation_result import CitationValidationResult


class CitationChecker:
    """Validate citation presence and well-formed source locators."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.require_version = bool(kwargs.get('require_version', True))
        self.require_page = bool(kwargs.get('require_page', False))

    def _is_valid(self, citation: object) -> bool:
        if citation is None:
            return False
        if isinstance(citation, Citation):
            if not str(getattr(citation, 'document_id', '') or '').strip():
                return False
            if self.require_page:
                page = getattr(citation, 'page_number', None)
                if page is None or int(page) < 1:
                    return False
            # Use shared validator
            if not is_citation_valid(citation):
                return False
            if self.require_version:
                version = getattr(citation, 'document_version', None)
                if version is None or not str(version).strip():
                    return False
            return True
        # Allow dict/strings?
        if isinstance(citation, dict):
            return bool(str(citation.get('document_id', '') or '').strip())
        if isinstance(citation, str):
            return bool(citation.strip())
        return bool(citation)

    def check(self, *args: object, **kwargs: object) -> CitationValidationResult:
        citations = _collect_citations(*args, **kwargs)
        invalid = [c for c in citations if not self._is_valid(c)]
        valid = len(citations) > 0 and not invalid
        errors = [f'invalid citation: {c!r}' for c in invalid]
        if not citations:
            errors = ['missing citation']
            valid = False
        has_citation = len(citations) > 0
        return CitationValidationResult(
            valid,
            has_citation=has_citation,
            citations=citations,
            invalid=invalid,
            errors=errors,
            reason=errors[0] if errors else None,
        )

    def is_valid(self, *args: object, **kwargs: object) -> object:
        # Single-citation convenience: return bool if one citation given
        citations = _collect_citations(*args, **kwargs)
        if len(citations) == 1:
            return self._is_valid(citations[0])
        return self.check(*args, **kwargs)

    def validate(self, *args: object, **kwargs: object) -> CitationValidationResult:
        return self.check(*args, **kwargs)

    def validate_citations(self, *args: object, **kwargs: object) -> CitationValidationResult:
        return self.check(*args, **kwargs)

    def check_citations(self, *args: object, **kwargs: object) -> CitationValidationResult:
        return self.check(*args, **kwargs)

    def check_presence(self, *args: object, **kwargs: object) -> bool:
        citations = _collect_citations(*args, **kwargs)
        return len(citations) > 0

    def has_citation(self, *args: object, **kwargs: object) -> bool:
        return self.check_presence(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> CitationValidationResult:
        return self.check(*args, **kwargs)


# Functions
def check_citation(*args: object, **kwargs: object) -> CitationValidationResult:
    return CitationChecker(*args, **{k: v for k, v in kwargs.items() if k in ('require_version', 'require_page')}).check(*args, **{k: v for k, v in kwargs.items() if k not in ('require_version', 'require_page')})


def validate_citation(*args: object, **kwargs: object) -> CitationValidationResult:
    return check_citation(*args, **kwargs)


CitationValidator = CitationChecker
CitationCheck = CitationChecker
__all__ = [
    'CitationCheck',
    'CitationChecker',
    'CitationValidationResult',
    'CitationValidator',
    'check_citation',
    'validate_citation',
]
