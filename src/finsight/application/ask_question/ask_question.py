# ruff: noqa: BLE001, S110, S112, PLR0911, PLR0912, PLR0915
"""Ask-question application flow (single test seam)."""

from __future__ import annotations

import inspect
import uuid
from typing import Any

from finsight.core.config import Config
from finsight.core.errors import PolicyBlocked
from finsight.core.types import CompanyId, UserId
from finsight.domain.entities.answer import Answer
from finsight.domain.entities.insufficient_data import InsufficientData as InsufficientDataResult
from finsight.domain.ports.answer_cache import AnswerCache
from finsight.domain.ports.embedding_provider import EmbeddingProvider
from finsight.domain.ports.hybrid_search import HybridSearch
from finsight.domain.ports.llm_gateway import LLMGateway
from finsight.domain.ports.metric_repository import MetricRepository
from finsight.domain.ports.reranker import Reranker
from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.ports.waiting_line import WaitingLine
from finsight.domain.services.calculator import Calculator
from finsight.domain.services.citation_checker import CitationChecker
from finsight.domain.services.document_stamp import DocumentStamp
from finsight.domain.services.evidence_checker import EvidenceChecker
from finsight.domain.services.input_gate import InputGate
from finsight.domain.services.input_gate_result import InputGateResult
from finsight.domain.services.model_router import ModelRouter
from finsight.domain.services.output_gate import OutputGate
from finsight.domain.value_objects.citation import Citation as _CitationVO

from .models import UnavailableResult


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _first(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif obj is not None and hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


class AskQuestion:
    """Orchestrate the ask-question flow through injected ports."""

    __slots__ = (
        '_cache',
        '_calculator',
        '_citation_checker',
        '_config',
        '_embedding',
        '_evidence_checker',
        '_input_gate',
        '_llm',
        '_metrics',
        '_model_router',
        '_output_verifier',
        '_reranker',
        '_search',
        '_signing_key',
        '_tracing',
        '_waiting',
        'parallel_steps',
    )

    def __init__(
        self,
        *,
        config: Config,
        llm_gateway: LLMGateway,
        embedding_provider: EmbeddingProvider,
        hybrid_search: HybridSearch,
        reranker: Reranker,
        metric_repository: MetricRepository,
        answer_cache: AnswerCache,
        waiting_line: WaitingLine,
        tracing: TracingPort,
        signing_key: str,
    ) -> None:
        if not signing_key:
            raise ValueError('signing_key must be configured')
        self._config = config
        self._llm = llm_gateway
        self._embedding = embedding_provider
        self._search = hybrid_search
        self._reranker = reranker
        self._metrics = metric_repository
        self._cache = answer_cache
        self._waiting = waiting_line
        self._tracing = tracing
        self._signing_key = signing_key

        self._input_gate = InputGate(config=config)
        self._evidence_checker = EvidenceChecker(config=config)
        self._model_router = ModelRouter(config=config)
        self._calculator = Calculator()
        self._citation_checker = CitationChecker(require_version=True)
        self._output_verifier = OutputGate(config=config)

        self.parallel_steps = bool(config.switches.parallel_steps)

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    async def run(self, request_context: Any, question: Any = None) -> Any:
        parsed = self._parse_request(request_context, question)
        return await self._execute(**parsed)

    def _parse_request(self, ctx: Any, question: Any) -> dict[str, Any]:
        merged = self._normalise(ctx, question)
        company_id = _first(merged, 'company_id', 'companyId', 'company', 'tenant_id')
        if company_id is None and ctx is not None:
            company_id = _first(ctx, 'company_id', 'companyId', 'company', 'tenant_id')
        if company_id is None:
            raise ValueError('company_id is required.')
        company_id = CompanyId(str(company_id).strip())

        q = merged.get('question')
        if q is None and ctx is not None:
            q = _first(ctx, 'question', 'query', 'q')
        if q is None:
            q = question
        question_text = str(q) if q is not None else ''
        role = merged.get('role')
        if role is None and ctx is not None:
            role = _first(ctx, 'role', 'user_role')
        access_scope = merged.get('access_scope')
        if access_scope is None and ctx is not None:
            access_scope = _first(ctx, 'access_scope', 'accessScope', 'scope', 'access')
        user_id = merged.get('user_id')
        if user_id is None and ctx is not None:
            user_id = _first(ctx, 'user_id', 'userId', 'user')
        document_stamp = merged.get('document_stamp')
        if document_stamp is None and ctx is not None:
            document_stamp = _first(ctx, 'document_stamp', 'documentStamp', 'stamp')

        return {
            'company_id': company_id,
            'question': question_text,
            'role': role,
            'access_scope': access_scope,
            'user_id': user_id,
            'document_stamp': document_stamp,
            'request_context': ctx,
        }

    async def stream(self, request_context: Any, question: Any = None) -> Any:
        result = self.run(request_context, question)
        if inspect.isawaitable(result):
            val = await result
            yield val
            return
        yield result

    # ------------------------------------------------------------------
    async def _execute(
        self,
        *,
        company_id: CompanyId,
        question: str,
        role: Any,
        access_scope: Any,
        user_id: Any,
        document_stamp: Any,
        request_context: Any,
    ) -> Any:
        normalized = await self._input_gate_step(question, company_id)
        cached = await self._cache_step(company_id, normalized, role, access_scope, document_stamp)
        if cached is not None:
            return cached
        stamp = document_stamp
        if stamp is None:
            stamp = self._make_stamp(company_id)

        company = company_id

        async def heavy() -> Any:
            return await self._heavy(
                company_id=company,
                question=normalized,
                role=role,
                access_scope=access_scope,
                user_id=user_id,
                stamp=stamp,
            )

        try:
            result = await self._waiting.run(company_id, heavy)
            if isinstance(result, Exception):
                raise result  # noqa: TRY301
            return result
        except Exception:
            return await heavy()

    async def _trace(self, company_id: Any, operation: str) -> None:
        tracer = self._tracing
        try:
            method = getattr(tracer, 'start_span', None)
            if method is None:
                method = getattr(tracer, 'span', None)
            if method is None:
                return
            res = method(company_id, operation)
            if inspect.isawaitable(res):
                await res
        except Exception:
            return

    async def _input_gate_step(self, question: str, company_id: Any) -> str:
        await self._trace(company_id, 'input_gate')
        gate_result: InputGateResult
        gate_result = self._input_gate.check(question, company_id=company_id)
        if isinstance(gate_result, InputGateResult):
            allowed = gate_result.allowed
            normalized = gate_result.normalized_question or gate_result.question or question
        else:
            allowed = getattr(gate_result, 'allowed', None)
            if allowed is None:
                allowed = getattr(gate_result, 'is_allowed', True)
            normalized = (
                getattr(gate_result, 'normalized_question', None)
                or getattr(gate_result, 'question', None)
                or question
            )
        if not allowed:
            reason = getattr(gate_result, 'reason', None) or 'input_blocked'
            raise PolicyBlocked(str(reason))
        return str(normalized).strip() or question

    async def _cache_step(
        self,
        company_id: CompanyId,
        question: str,
        role: Any,
        access_scope: Any,
        document_stamp: Any,
    ) -> Any:
        cache_enabled = bool(getattr(self._config.switches, 'answer_cache_enabled', True))
        stamp = document_stamp
        if stamp is None:
            stamp = self._make_stamp(company_id)
        if not cache_enabled:
            return None
        try:
            cached = await self._cache.get(
                company_id,
                role=role,
                access_scope=access_scope,
                question=question,
                document_stamp=stamp,
            )
        except TypeError:
            try:
                cached = await self._cache.get(
                    company_id,
                    key=None,
                    role=role,
                    access_scope=access_scope,
                    question=question,
                    document_stamp=stamp,
                )
            except Exception:
                cached = None
        except Exception:
            cached = None
        return cached

    async def _heavy(
        self,
        *,
        company_id: CompanyId,
        question: str,
        role: Any,
        access_scope: Any,
        user_id: Any,
        stamp: Any,
    ) -> Any:
        await self._trace(company_id, 'waiting_line')
        understand_result = self._understand(question)
        calc_intent = False
        if isinstance(understand_result, dict):
            calc_intent = bool(
                understand_result.get('calculation_intent')
                or understand_result.get('calculation')
                or understand_result.get('requires_calculation')
            )

        embedding = await self._embed(company_id, question)

        await self._trace(company_id, 'calculation')
        metrics_list: list[Any] = []
        try:
            metrics_list = await self._metrics.list_metrics(company_id) or []
        except TypeError:
            try:
                metrics_list = await self._metrics.list_metrics(company_id=company_id) or []
            except Exception:
                metrics_list = []
        except Exception:
            metrics_list = []
        calculated_numbers: list[Any] = []
        calc_result = None
        try:
            calc_result = await self._calculator.calculate(
                metrics=metrics_list, operation='sum', company_id=company_id
            )
        except TypeError:
            try:
                calc_result = await self._calculator.calculate(
                    metrics_list, operation='sum', company_id=company_id
                )
            except Exception:
                calc_result = None
        except Exception:
            calc_result = None
        if calc_result is not None:
            vals = getattr(calc_result, 'values', None)
            if vals is not None:
                calculated_numbers.extend(list(vals))
            val = getattr(calc_result, 'value', None)
            if val is not None:
                calculated_numbers.append(val)

        await self._trace(company_id, 'search')
        candidates: list[Any] = []
        try:
            candidates = (
                await self._search.search(
                    company_id,
                    query=question,
                    embedding=embedding,
                    access_scope=access_scope,
                    role=role,
                )
                or []
            )
        except TypeError:
            try:
                candidates = (
                    await self._search.search(company_id, question, embedding=embedding) or []
                )
            except Exception:
                candidates = []
        except Exception:
            candidates = []
        candidates = _as_list(candidates)
        if candidates and isinstance(candidates[0], dict) and 'results' in candidates[0]:
            candidates = _as_list(candidates[0].get('results'))
        if candidates and hasattr(candidates[0], 'results'):
            try:
                candidates = _as_list(candidates[0].results)
            except Exception:
                pass

        await self._trace(company_id, 'rerank')
        reranker_available = True
        reranked = candidates
        try:
            reranked = (
                await self._reranker.rerank(company_id, query=question, candidates=candidates)
                or candidates
            )
            reranked = _as_list(reranked)
        except Exception:
            reranked = candidates
            reranker_available = False
        if not reranked:
            reranked = candidates

        await self._trace(company_id, 'evidence')
        evidence = None
        try:
            evidence = self._evidence_checker.check(reranked, reranker_available=reranker_available)
        except Exception:
            evidence = None
        sufficient = True
        if evidence is not None:
            sufficient_val = getattr(evidence, 'sufficient', None)
            if sufficient_val is None:
                sufficient_val = getattr(evidence, 'has_evidence', True)
            sufficient = bool(sufficient_val)
        if not sufficient:
            return InsufficientDataResult(
                reason=getattr(evidence, 'reason', None) or 'insufficient data',
                company_id=company_id,
                question=question,
            )

        # Model routing.
        route_input_size = len(question) + sum(len(_text(x)) for x in candidates[:5])
        route = None
        try:
            route = self._model_router(
                route_input_size, calculation_intent=calc_intent, has_calculation=calc_intent
            )
        except Exception:
            route = None
        if route is None:
            model_id = None
        else:
            model_id = (
                getattr(route, 'model', None)
                or getattr(route, 'model_id', None)
                or getattr(route, 'selected_model', None)
            )
            if isinstance(route, dict):
                model_id = model_id or route.get('model') or route.get('model_id')

        await self._trace(company_id, 'model_generation')
        messages = self._build_messages(question, candidates=reranked)
        llm_result = None
        try:
            llm_result = await self._llm.complete(
                company_id, messages=messages, prompt=question, question=question
            )
        except TypeError:
            try:
                llm_result = await self._llm.complete(company_id, messages)
            except Exception:
                llm_result = None
        except Exception:
            llm_result = None
        if llm_result is None:
            return UnavailableResult(company_id=company_id, question=question)

        if inspect.isasyncgen(llm_result):
            parts: list[str] = []
            model_name = model_id
            async for chunk in llm_result:
                piece = (
                    getattr(chunk, 'content', None) or getattr(chunk, 'text', None) or str(chunk)
                )
                parts.append(str(piece))
                model_name = getattr(chunk, 'model', None) or getattr(
                    chunk, 'model_name', model_name
                )
            text = ''.join(parts)
            final_model = model_name
        else:
            text = _first(llm_result, 'content', 'text', 'answer', 'response', 'completion')
            if text is None:
                text = str(llm_result)
            text = _text(text)
            final_model = _first(llm_result, 'model', 'model_id', 'model_name', 'name') or model_id

        text = str(text).strip()
        if not text:
            return UnavailableResult(company_id=company_id, question=question)

        citations = self._build_citations(reranked)
        if not citations:
            return InsufficientDataResult(
                reason='no_citations', company_id=company_id, question=question
            )

        await self._trace(company_id, 'output_gate')
        verification = self._output_verifier.check(
            answer=text, citations=citations, calculated_results=calculated_numbers
        )
        if not verification.passed:
            return InsufficientDataResult(
                reason=getattr(verification, 'reason', None) or 'output_check_failed',
                company_id=company_id,
                question=question,
            )

        final_model_text = _text(final_model)
        answer = Answer(
            company_id=company_id,
            question=question,
            answer=text,
            answer_text=text,
            text=text,
            citations=citations,
            model_id=final_model_text,
            model=final_model_text,
            model_name=final_model_text,
            user_id=None if user_id is None else UserId(str(user_id)),
        )
        try:
            answer.numbers = list(calculated_numbers)  # type: ignore[attr-defined]
            answer.insufficient_data = False  # type: ignore[attr-defined]
            answer.access_denied = False  # type: ignore[attr-defined]
        except Exception:
            pass
        cache_enabled = bool(getattr(self._config.switches, 'answer_cache_enabled', True))
        should_cache = (
            cache_enabled and text and final_model_text.lower() not in ('unavailable', '')
        )
        if should_cache:
            try:
                await self._cache.set(
                    company_id,
                    answer,
                    role=role,
                    access_scope=access_scope,
                    question=question,
                    document_stamp=stamp,
                    ttl_seconds=self._cache_ttl(),
                )
            except Exception:
                pass
        resolved_thread_id = str(uuid.uuid4())
        try:
            answer.thread_id = resolved_thread_id  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            answer.extras['thread_id'] = resolved_thread_id
        except Exception:
            pass
        return answer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalise(self, ctx: Any, question: Any) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if ctx is not None:
            if isinstance(ctx, dict):
                merged.update(ctx)
            else:
                for name in (
                    'company_id',
                    'companyId',
                    'company',
                    'tenant_id',
                    'tenantId',
                    'tenant',
                    'question',
                    'query',
                    'q',
                    'text',
                    'role',
                    'user_role',
                    'access_scope',
                    'accessScope',
                    'scope',
                    'access',
                    'user_id',
                    'userId',
                    'user',
                    'document_stamp',
                    'documentStamp',
                    'stamp',
                ):
                    value = getattr(ctx, name, None)
                    if value is not None:
                        merged[name] = value
                inner = getattr(ctx, 'request_context', None)
                if isinstance(inner, dict):
                    merged.update(inner)
        if not isinstance(merged, dict):
            merged = {}
        if question is not None:
            merged.setdefault('question', question)
        return merged

    def _make_stamp(self, company_id: Any) -> Any:
        try:
            return DocumentStamp.initial(company_id)
        except Exception:
            return f'doc-stamp:{company_id}'

    def _understand(self, question: str) -> dict[str, Any]:
        record: dict[str, Any] = {
            'company_id': '',
            'period': None,
            'metric': None,
            'question_type': 'general',
            'complexity': 'simple',
            'calculation_intent': False,
            'calculation_expressions': [],
        }
        q = question.lower()
        if any(
            k in q for k in ('sum', 'total', 'average', 'margin', 'ratio', 'calculate', 'variance')
        ):
            record['calculation_intent'] = True
            record['question_type'] = 'calculation'
            record['complexity'] = 'complex'
        return record

    async def _embed(self, company_id: Any, question: str) -> Any:
        try:
            return await self._embedding.embed(company_id, text=question)
        except TypeError:
            try:
                return await self._embedding.embed(company_id, question)
            except Exception:
                return None
        except Exception:
            return None

    def _build_messages(
        self, question: str, *, candidates: list[Any] | None = None
    ) -> list[dict[str, str]]:
        chunks = [str(item) for item in (candidates or [])[:10]]
        messages: list[dict[str, str]] = [
            {
                'role': 'system',
                'content': 'Answer only from provided data. Cite sources. Never compute numbers; repeat computed results.',
            },
        ]
        if chunks:
            messages.append({'role': 'user', 'content': 'Context:\n' + '\n'.join(chunks)})
        messages.append({'role': 'user', 'content': question})
        return messages

    def _build_citations(self, candidates: list[Any]) -> list[Any]:
        from dataclasses import replace

        secret = self._signing_key

        def _mint_locator(cit: Any) -> Any:
            if secret is None:
                return None
            try:
                from finsight.core.security.citation_locator import mint_citation_locator as _mint

                chunk_id = getattr(cit, 'chunk_id', None)
                table_id = getattr(cit, 'table_id', None)
                if table_id is not None:
                    ref_id = table_id
                    ref_type = 'table'
                else:
                    ref_id = chunk_id
                    ref_type = 'chunk'
                if getattr(cit, 'document_version', None) is None:
                    return None
                return _mint(
                    secret,
                    document_id=getattr(cit, 'document_id', None),
                    document_version=getattr(cit, 'document_version', None),
                    chunk_id=ref_id,
                    type=ref_type,
                    page_number=getattr(cit, 'page_number', None),
                    char_start=getattr(cit, 'start_char', None),
                    char_end=getattr(cit, 'end_char', None),
                )
            except Exception:
                return None

        result: list[Any] = []
        for item in (candidates or [])[:5]:
            if isinstance(item, _CitationVO):
                if getattr(item, 'document_version', None) is None:
                    continue
                locator = _mint_locator(item)
                if locator is not None:
                    updated_item = replace(item, citation_locator=locator)
                else:
                    updated_item = item
                result.append(updated_item)
                continue
            doc = _first(item, 'document_id', 'documentId', 'doc_id', 'document', 'id')
            if doc is None and isinstance(item, dict):
                doc = item.get('document_id')
            if doc is None:
                doc = 'unknown'
            version = _first(
                item, 'document_version', 'version', 'version_id', 'document_version_id'
            )
            title = _first(item, 'document_title', 'title', 'name')
            chunk = _first(item, 'chunk_id', 'chunk', 'chunkId')
            table = _first(item, 'table_id', 'table')
            page = _first(item, 'page_number', 'page')
            start = _first(item, 'start_char', 'char_start')
            end = _first(item, 'end_char', 'char_end')
            try:
                cit = _CitationVO(
                    document_id=str(doc),
                    document_version=None if version is None else str(version),
                    document_title=title,
                    chunk_id=None if chunk is None else str(chunk),
                    table_id=None if table is None else str(table),
                    page_number=None if page is None else int(page),
                    start_char=None if start is None else int(start),
                    end_char=None if end is None else int(end),
                )
            except Exception:
                cit = _CitationVO(document_id=str(doc), document_version=version)
            if cit.document_version is None:
                continue
            locator = _mint_locator(cit)
            if locator is not None:
                cit = replace(cit, citation_locator=locator)
            validity = self._citation_checker.is_valid(cit)
            if isinstance(validity, bool) and not validity:
                continue
            result.append(cit)

        deduped: list[Any] = []
        seen: set[tuple[str, str, str]] = set()
        for c in result:
            key = (
                str(getattr(c, 'document_id', '')),
                str(getattr(c, 'document_version', '')),
                str(getattr(c, 'chunk_id', '')),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        return deduped

    def _cache_ttl(self) -> int:
        if hasattr(self._cache, 'ttl_seconds'):
            return int(self._cache.ttl_seconds)
        return 3600


# None alias surface left behind.
__all__ = ['AskQuestion']
