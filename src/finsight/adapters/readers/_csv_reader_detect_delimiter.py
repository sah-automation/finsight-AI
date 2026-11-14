"""CSV/TSV reader adapter implementing :class:`DocumentReader`.

Uses ``csv.Sniffer`` for delimiter detection, strips a UTF-8 BOM, skips
empty lines and preserves the header row. Tabular data is emitted as a single
table and a single virtual page paired with a concrete row-range locator so
citations stay meaningful beyond "Page 1".
"""

from __future__ import annotations

import csv
from typing import Any


def _detect_delimiter(self: Any, sample: str) -> Any:
    if not sample.strip():
        return ','

    # Honour an unambiguous tab-separated input first.
    if sample.count('\t') > 0:
        try:
            lines = [ln for ln in sample.splitlines() if ln.strip()]
            parsed = list(csv.reader(lines, delimiter='\t'))
            if parsed and all(len(r) > 1 for r in parsed) and len({len(r) for r in parsed}) == 1:
                return '\t'
        except csv.Error:
            pass

    try:
        dialect = csv.Sniffer().sniff(sample + '\n', delimiters=',\t;|')
        if getattr(dialect, 'delimiter', None):
            return str(dialect.delimiter)
    except csv.Error:
        pass

    # Fallback that respects quoted fields: evaluate each candidate by
    # parsing the sample and preferring a delimiter that yields a consistent
    # multi-column shape across every non-empty line.
    candidates = (',', '\t', ';', '|')
    best_delim = ','
    best_score = (-1, -1)  # (column_count, consistent_row_count)
    for delim in candidates:
        try:
            rows = list(csv.reader(sample.splitlines(), delimiter=delim))
            rows = [r for r in rows if any(str(c).strip() != '' for c in r)]
            if not rows:
                continue
            counts: dict[int, int] = {}
            for row in rows:
                counts[len(row)] = counts.get(len(row), 0) + 1
            top_cols = max(counts)
            consistent = counts.get(top_cols, 0)
            if top_cols <= 1:
                continue
            score = (top_cols, consistent)
            if score > best_score:
                best_score = score
                best_delim = delim
        except csv.Error:
            continue

    if best_score[0] <= 1:
        # Last resort: raw counts (may be imprecise for quoted fields).
        tab_count = sample.count('\t')
        if tab_count > 0:
            return '\t'
        raw_counts: dict[str, int] = {d: sample.count(d) for d in (',', ';', '|')}
        best = max(raw_counts, key=lambda d: raw_counts[d])
        return best if raw_counts[best] > 0 else ','
    return best_delim
