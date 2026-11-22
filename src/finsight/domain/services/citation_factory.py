"""Citation factory - builds CitationIds from Metric provenance (issue #397).

A CitationId identifies the exact location in a document version where a Metric
was extracted. It is distinct from the Metric ID, which identifies the figure
itself. Two Metrics can share a CitationId (same table), and a Metric can be
re-extracted while its location stays the same.

Format: cit:v1:{document_version_id}:p{page}[:t{table_id}][:c{chunk_id}][:o{start}-{end}]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.domain.entities.metric import Metric


class CitationFactory:
    """Build CitationIds from Metric provenance without I/O."""

    def __init__(self) -> None:
        pass

    def build_from_metric(self, metric: Metric) -> str | None:
        """Build a CitationId from a single Metric's provenance.

        Returns None if the Metric lacks the minimum required provenance
        (document_version_id and page). The caller should treat a missing
        citation as "needs_review" for the KPI.
        """
        base = self._get_base_parts(metric)
        if base is None:
            return None
        return ':'.join(self._add_optional_parts(base, metric))

    def _get_base_parts(self, metric: Metric) -> list[str] | None:
        document_version_id = self._get_document_version_id(metric)
        if not document_version_id:
            return None
        page = self._get_page(metric)
        if not page:
            return None
        return ['cit:v1', str(document_version_id), f'p{page}']

    def _add_optional_parts(self, parts: list[str], metric: Metric) -> list[str]:
        table_id = self._get_table_id(metric)
        if table_id:
            parts.append(f't{table_id}')
        chunk_id = self._get_chunk_id(metric)
        if chunk_id:
            parts.append(f'c{chunk_id}')
        char_range = self._get_char_range(metric)
        if char_range:
            parts.append(f'o{char_range[0]}-{char_range[1]}')
        return parts

    def build_from_metrics(self, metrics: Sequence[Metric]) -> list[str]:
        """Build CitationIds from multiple Metrics, sorted and deduplicated.

        Metrics that lack required provenance are silently skipped (their
        absence will be reflected in the KPI's computation_status).
        """
        citations: set[str] = set()
        for metric in metrics or ():
            if metric is None:
                continue
            cit = self.build_from_metric(metric)
            if cit:
                citations.add(cit)
        return sorted(citations)

    def _get_document_version_id(self, metric: Metric) -> str | None:
        """Extract document_version_id from Metric."""
        # Try the dedicated field first, then fall back to document_version
        dv_id = getattr(metric, 'document_version_id', None)
        if dv_id:
            return str(dv_id)
        dv_id = getattr(metric, 'version_id', None)
        if dv_id:
            return str(dv_id)
        # Check source_location dict
        source_location = getattr(metric, 'source_location', None)
        if isinstance(source_location, Mapping):
            dv_id = source_location.get('document_version_id')
            if dv_id:
                return str(dv_id)
        return None

    def _get_page(self, metric: Metric) -> int | None:
        """Extract page number from Metric's source_location."""
        # Try dedicated attributes first
        for attr in ('source_page', 'page_number', 'page'):
            val = getattr(metric, attr, None)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass

        # Fall back to source_location dict
        source_location = getattr(metric, 'source_location', None)
        if isinstance(source_location, Mapping):
            for key in ('page', 'page_number'):
                val = source_location.get(key)
                if val is not None:
                    try:
                        return int(val)
                    except (TypeError, ValueError):
                        pass
        return None

    def _get_table_id(self, metric: Metric) -> str | None:
        """Extract table_id from Metric's source_location."""
        for attr in ('source_table', 'table_id', 'table'):
            val = getattr(metric, attr, None)
            if val:
                return str(val)

        source_location = getattr(metric, 'source_location', None)
        if isinstance(source_location, Mapping):
            for key in ('table', 'table_id'):
                val = source_location.get(key)
                if val:
                    return str(val)
        return None

    def _get_chunk_id(self, metric: Metric) -> str | None:
        """Extract chunk_id from Metric's source_location."""
        for attr in ('source_chunk_id', 'chunk_id', 'chunk'):
            val = getattr(metric, attr, None)
            if val:
                return str(val)

        source_location = getattr(metric, 'source_location', None)
        if isinstance(source_location, Mapping):
            for key in ('chunk', 'chunk_id'):
                val = source_location.get(key)
                if val:
                    return str(val)
        return None

    def _get_char_range(self, metric: Metric) -> tuple[int, int] | None:
        """Extract character range from Metric's source_location."""
        start = None
        end = None

        for attr in ('start_char', 'char_start'):
            val = getattr(metric, attr, None)
            if val is not None:
                try:
                    start = int(val)
                    break
                except (TypeError, ValueError):
                    pass

        for attr in ('end_char', 'char_end'):
            val = getattr(metric, attr, None)
            if val is not None:
                try:
                    end = int(val)
                    break
                except (TypeError, ValueError):
                    pass

        source_location = getattr(metric, 'source_location', None)
        if isinstance(source_location, Mapping):
            if start is None:
                for key in ('start_char', 'char_start'):
                    val = source_location.get(key)
                    if val is not None:
                        try:
                            start = int(val)
                            break
                        except (TypeError, ValueError):
                            pass
            if end is None:
                for key in ('end_char', 'char_end'):
                    val = source_location.get(key)
                    if val is not None:
                        try:
                            end = int(val)
                            break
                        except (TypeError, ValueError):
                            pass

        if start is not None and end is not None:
            return (start, end)
        return None


__all__ = ['CitationFactory']
