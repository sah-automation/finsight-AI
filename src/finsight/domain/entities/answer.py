"""Answer entity - a question answer that cannot exist without a citation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from finsight.core.types import AnswerId, CompanyId, UserId
from finsight.domain.services.evidence import is_citation_valid
from finsight.domain.value_objects.citation import Citation


def _now() -> datetime:
    return datetime.now(UTC)


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _require_citations(value: object) -> list[Citation]:
    citations: list[Citation] = []
    for item in _as_list(value):
        if item is None:
            continue
        if not isinstance(item, Citation) or not is_citation_valid(item):
            raise ValueError('Answer requires at least one valid citation')
        citations.append(item)
    if not citations:
        raise ValueError('Answer requires at least one valid citation')
    return citations


class Answer:
    """A question answer with provenance through citations.

    ``Answer`` cannot be constructed without at least one valid citation.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        positional = [
            'answer_id',
            'company_id',
            'question',
            'answer',
            'citations',
            'user_id',
            'model_id',
            'model',
            'model_name',
            'created_at',
            'updated_at',
        ]
        data: dict[str, object] = dict.fromkeys(positional)
        data['citations'] = None

        for index, value in enumerate(args):
            if index < len(positional):
                data[positional[index]] = value

        def coalesce(*names: str, default: object = None) -> object:
            for name in names:
                if name in kwargs and kwargs[name] is not None:
                    return kwargs[name]
            for name in names:
                if data.get(name) is not None:
                    return data.get(name)
            return default

        ident = coalesce('answer_id', 'id', 'answerId', 'answerID', default=None)
        if ident is None:
            ident = str(__import__('uuid').uuid4())
        company_id = coalesce('company_id', 'companyId', 'tenant_id', 'tenantId', default=None)
        question = coalesce('question', 'query', 'user_question', default=None)
        answer_text = coalesce(
            'answer',
            'answer_text',
            'text',
            'content',
            'response',
            default=None,
        )
        citations = coalesce(
            'citations',
            'citation',
            'citations_list',
            'sources',
            default=None,
        )
        user_id = coalesce('user_id', 'userId', 'author_id', default=None)
        model_id = coalesce('model_id', 'modelId', 'model', 'model_name', 'modelId', default=None)
        created_at = coalesce('created_at', 'createdAt', 'timestamp', default=None)
        updated_at = coalesce('updated_at', 'updatedAt', default=None)

        citations_list = _require_citations(citations)

        if created_at is None:
            created_at = _now()
        if updated_at is None:
            updated_at = created_at

        self.answer_id = AnswerId(str(ident))
        self.id = self.answer_id
        self.company_id = None if company_id is None else CompanyId(str(company_id))
        self.question = '' if question is None else str(question)
        self.answer = '' if answer_text is None else str(answer_text)
        self.answer_text = self.answer
        self.text = self.answer
        self.content = self.answer
        self.response = self.answer
        self.citations = citations_list
        self.citation = citations_list
        self.user_id = None if user_id is None else UserId(str(user_id))
        self.model_id = None if model_id is None else str(model_id)
        self.model = self.model_id
        self.model_name = self.model_id
        self.created_at = created_at
        self.updated_at = updated_at
        self.metadata = kwargs.get('metadata') if isinstance(kwargs.get('metadata'), dict) else {}
        # Keep any extras mirrored for compatibility.
        self.extras = {}
        for key, value in kwargs.items():
            if key not in {
                'answer_id',
                'id',
                'company_id',
                'question',
                'answer',
                'answer_text',
                'text',
                'content',
                'response',
                'citations',
                'citation',
                'user_id',
                'model_id',
                'model',
                'model_name',
                'created_at',
                'updated_at',
                'metadata',
            }:
                self.extras[key] = value

    def __repr__(self) -> str:
        return f'Answer(answer_id={self.answer_id!r}, citations={self.citations!r})'


__all__ = ['Answer']
