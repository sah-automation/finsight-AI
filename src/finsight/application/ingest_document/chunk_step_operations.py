"""Helpers for ChunkStep."""

from __future__ import annotations

from typing import Any

from finsight.domain.entities.chunk import Chunk as ChunkEntity
from finsight.domain.services.delta_differ import DeltaDiffer
from finsight.domain.value_objects.reader_result import ReaderResult

from .pipeline_step_worker import PipelineStepWorker, _awaitv, _get


def _get_chars_per_token(config: Any) -> int:
    """Get chars_per_token from config, defaulting to 4 (ModelRouter default)."""
    if config is None:
        return 4
    # Check nested config structures
    ingestion = getattr(config, 'ingestion', None) or (
        config.get('ingestion', {}) if isinstance(config, dict) else {}
    )
    if ingestion and 'chars_per_token' in ingestion:
        try:
            return int(ingestion['chars_per_token'])
        except (TypeError, ValueError):
            pass
    # Also check llm.embedding_model.chars_per_token
    llm = getattr(config, 'llm', None) or (
        config.get('llm', {}) if isinstance(config, dict) else {}
    )
    if llm:
        emb = llm.get('embedding_model', llm.get('embedding', {})) if isinstance(llm, dict) else {}
        if isinstance(emb, dict) and 'chars_per_token' in emb:
            try:
                return int(emb['chars_per_token'])
            except (TypeError, ValueError):
                pass
    # Check ModelRouter-style kwargs
    if hasattr(config, 'chars_per_token'):
        try:
            return int(config.chars_per_token)
        except (TypeError, ValueError):
            pass
    return 4


def _estimate_token_count(text: str, chars_per_token: int) -> int:
    """Estimate token count from text using character-based approximation.

    Uses the provided chars_per_token ratio (default 4 chars/token).
    Returns 0 for empty text, otherwise ceiling division.
    """
    if not text:
        return 0
    return max(1, (len(text) + chars_per_token - 1) // chars_per_token)


def _extract_text(reader_result: Any) -> str:
    """Extract text from reader_result (ReaderResult or dict)."""
    try:
        if isinstance(reader_result, ReaderResult):
            return reader_result.text
        text: Any = _get(reader_result, 'text', default=None)
        if text is None:
            return str(reader_result or '')
        return str(text)
    except Exception:  # noqa: BLE001
        return str(reader_result or '')


def _resolve_document_id(version: Any, document_id: Any) -> Any:
    """Resolve document_id from version or fall back to provided document_id or version_id."""
    resolved = _get(version, 'document_id', 'documentId', default=None) or document_id
    if resolved is None:
        return version
    return resolved


def _get_page_numbers(reader_result: Any) -> list[Any]:
    """Get page_numbers from reader_result."""
    page_numbers: Any = getattr(reader_result, 'page_numbers', None)
    if page_numbers is None:
        return list(_get(reader_result, 'page_numbers', 'pages', default=[]) or [])
    return list(page_numbers)


class ChunkStepOperations(PipelineStepWorker):
    chunk_repository: Any
    state_store: Any
    delta_tracking: Any
    config: Any

    def _build_chunks(
        self,
        reader_result: Any,
        company_id: Any,
        document_id: Any,
        version_id: Any,
        version: Any,
        ctx: Any,
    ) -> tuple[list[str], list[ChunkEntity]]:
        text = _extract_text(reader_result)
        chunks = self._chunk_text(str(text or ''))
        try:
            ctx.chunks = chunks
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['chunks'] = chunks
        resolved_document_id = _resolve_document_id(version, document_id)
        page_numbers = _get_page_numbers(reader_result)
        chunk_entities = []
        occurrence_counts: dict[tuple[tuple[str, ...], str], int] = {}
        chars_per_token = _get_chars_per_token(self.config)
        for index, chunk_text in enumerate(chunks):
            structure_path = ()
            occurrence_key = (structure_path, chunk_text)
            occurrence = occurrence_counts.get(occurrence_key, 0)
            occurrence_counts[occurrence_key] = occurrence + 1
            page_number = None
            if isinstance(page_numbers, (list, tuple)) and index < len(page_numbers):
                page_number = page_numbers[index]
            try:
                chunk_entities.append(
                    ChunkEntity.create(
                        company_id=company_id,
                        document_id=resolved_document_id,
                        version_id=version_id,
                        text=chunk_text,
                        ordinal=index,
                        occurrence=occurrence,
                        structure_path=structure_path,
                        page_number=page_number,
                        token_count=_estimate_token_count(chunk_text, chars_per_token),
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return chunks, chunk_entities

    async def _compute_chunk_diff(
        self,
        chunk_entities: list[ChunkEntity],
        company_id: Any,
        document_id: Any,
        version_id: Any,
        delta_flag: bool,
    ) -> tuple[list[Any], list[ChunkEntity], int, Any]:
        removed_chunk_ids = []
        changed_entities = list(chunk_entities)
        unchanged_count = 0
        chunk_diff = None
        if delta_flag and chunk_entities:
            resolved_document_id = document_id if document_id is not None else version_id
            try:
                previous_version_id = await self._previous_committed_version_id(
                    company_id, resolved_document_id, version_id
                )
            except Exception:  # noqa: BLE001
                previous_version_id = None
            previous_chunks: list[ChunkEntity] = []
            if previous_version_id is not None and self.chunk_repository is not None:
                try:
                    previous_chunks = (
                        await _awaitv(
                            self.chunk_repository.list_chunks_by_version(
                                company_id, previous_version_id, include_inactive=False
                            )
                        )
                        or []
                    )
                except Exception:  # noqa: BLE001
                    previous_chunks = []
            if previous_chunks:
                try:
                    diff = DeltaDiffer().diff_chunks(previous_chunks, chunk_entities)
                    chunk_diff = diff
                    changed_ids = set(getattr(diff, 'added', ()) + getattr(diff, 'changed', ()))
                    changed_entities = [
                        c for c in chunk_entities if c.chunk_id in changed_ids
                    ] or list(chunk_entities)
                    removed_chunk_ids = list(getattr(diff, 'removed', ()))
                    unchanged_count = len(getattr(diff, 'unchanged', ()))
                except Exception:  # noqa: BLE001
                    changed_entities = list(chunk_entities)
            else:
                changed_entities = list(chunk_entities)
        if not delta_flag:
            changed_entities = list(chunk_entities)
        return removed_chunk_ids, changed_entities, unchanged_count, chunk_diff

    def _augment_context(
        self,
        ctx: Any,
        reader_result: Any,
        chunks: list[str],
        chunk_entities: list[ChunkEntity],
        payload: tuple[list[ChunkEntity], list[Any], bool, Any, int],
    ) -> None:
        changed_entities, removed_chunk_ids, delta_flag, chunk_diff, unchanged_count = payload
        branch = 'delta' if delta_flag else 'full_reprocess'
        changed_chunks = [c.text for c in changed_entities]
        embed_chunks = [c.text for c in changed_entities]
        updates = {
            'reader_result': reader_result,
            'chunks': chunks,
            'chunk_entities': chunk_entities,
            'changed_chunk_entities': changed_entities,
            'changed_entities': changed_entities,
            'changed_chunks': changed_chunks,
            'embed_chunks': embed_chunks,
            'removed_chunk_ids': removed_chunk_ids,
            'removed_ids': removed_chunk_ids,
            'chunk_count': len(chunks),
            'chunks_count': len(chunks),
            'changed_count': len(changed_entities),
            'removed_count': len(removed_chunk_ids),
            'unchanged_count': unchanged_count,
            'unchanged': unchanged_count,
            'delta_tracking': bool(delta_flag),
            'chunk_diff': chunk_diff,
            'branch': branch,
            'delta_branch': branch,
            'status': 'processing',
        }
        for key, value in updates.items():
            try:
                setattr(ctx, key, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[key] = value
        try:
            ctx.previous_version_id = None
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['previous_version_id'] = None
