'use client';

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { Button } from '@/components/ui/button';
import { InlineNotice } from '@/components/ui/inline-notice';
import { messages } from '@/lib/messages';
import {
  fetchOriginalDocument,
  fetchSourceViewer,
  reportWrongSource,
  type SourceViewerCitation,
  type SourceViewerHighlight,
  type SourceViewerResponse,
  type SourceViewerTable,
} from '@/lib/api/events';

export interface SourceViewerProps {
  citation: SourceViewerCitation;
  isOpen: boolean;
  onClose: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onNewerVersion?: () => void;
  hasNext?: boolean;
  hasPrevious?: boolean;
  totalCitations?: number;
  currentCitationIndex?: number;
}

type SourceViewerState = 'loading' | 'error' | 'success' | 'not_available';

function getText(record: SourceViewerResponse | null | undefined, ...names: string[]): string | undefined {
  if (!record) return undefined;
  for (const name of names) {
    const value = record[name as keyof SourceViewerResponse];
    if (typeof value === 'string' && value) {
      return value;
    }
  }
  return undefined;
}

function getNumber(record: SourceViewerResponse | null | undefined, ...names: string[]): number | undefined {
  if (!record) return undefined;
  for (const name of names) {
    const value = record[name as keyof SourceViewerResponse];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return undefined;
}

function getBoolean(record: SourceViewerResponse | null | undefined, ...names: string[]): boolean | undefined {
  if (!record) return undefined;
  for (const name of names) {
    const value = record[name as keyof SourceViewerResponse];
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function formatTable(table: SourceViewerTable): React.ReactNode {
  const headers = table.headers ?? [];
  const rows = table.rows ?? [];

  if (!headers.length && !rows.length) {
    return <pre className="text-xs text-secondary whitespace-pre-wrap">{table.text ?? ''}</pre>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        {headers.length > 0 && (
          <thead className="bg-subtle border-b border-line">
            <tr>
              {headers.map((header, i) => (
                <th key={i} className="px-3 py-2 text-left text-xs font-medium uppercase text-secondary">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-line">
              {Array.isArray(row)
                ? row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 text-primary">
                      {String(cell)}
                    </td>
                  ))
                : Object.entries(row).map(([key, value]) => (
                    <td key={key} className="px-3 py-2 text-primary">
                      {String(value)}
                    </td>
                  ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function highlightText(text: string, highlight: SourceViewerHighlight | null | undefined): React.ReactNode {
  if (!highlight || !text) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }

  const start = highlight.start_char ?? highlight.char_start ?? highlight.start ?? highlight.s ?? 0;
  const end = highlight.end_char ?? highlight.char_end ?? highlight.end ?? highlight.e ?? 0;
  const safeStart = Math.max(0, Math.min(start, text.length));
  const safeEnd = Math.max(safeStart, Math.min(end, text.length));

  const before = text.slice(0, safeStart);
  const highlighted = text.slice(safeStart, safeEnd);
  const after = text.slice(safeEnd);

  return (
    <span className="whitespace-pre-wrap">
      {before}
      <mark tabIndex={0} className="bg-highlight px-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface">{highlighted}</mark>
      {after}
    </span>
  );
}

function getScrollTarget(highlight: SourceViewerHighlight | null | undefined): number | null {
  if (!highlight) return null;
  return highlight.start_char ?? highlight.char_start ?? highlight.start ?? highlight.s ?? null;
}

export function SourceViewer({
  citation,
  isOpen,
  onClose,
  onNext,
  onPrevious,
  onNewerVersion,
  hasNext,
  hasPrevious,
  totalCitations,
  currentCitationIndex,
}: SourceViewerProps) {
  const [state, setState] = useState<SourceViewerState>('loading');
  const [data, setData] = useState<SourceViewerResponse | null>(null);
  const [originalLoading, setOriginalLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [reported, setReported] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const scrollDoneRef = useRef(false);

  const isLoading = state === 'loading';
  const isNotAvailable = state === 'not_available';
  const isError = state === 'error';

  const documentTitle = useMemo(
    () => getText(data!, 'document_title', 'title') ?? citation.document_title ?? 'Document',
    [data, citation.document_title],
  );
  const version = useMemo(
    () => getText(data!, 'document_version', 'version', 'version_id') ?? String(citation.document_version ?? ''),
    [data, citation.document_version],
  );
  const page = useMemo(
    () => getNumber(data!, 'page_number', 'page') ?? Number(citation.page_number ?? NaN),
    [data, citation.page_number],
  );
  const category = useMemo(
    () => getText(data!, 'category', 'document_category') ?? citation.category ?? '',
    [data, citation.category],
  );
  const period = useMemo(
    () => getText(data!, 'period', 'document_period') ?? citation.period ?? '',
    [data, citation.period],
  );
  const documentStatus = useMemo(
    () => getText(data!, 'document_status', 'status') ?? citation.document_status ?? '',
    [data, citation.document_status],
  );
  const needsReview = useMemo(() => getBoolean(data!, 'needs_review') ?? false, [data]);
  const newerVersionAvailable = useMemo(
    () => getBoolean(data!, 'newer_version_available') ?? false,
    [data],
  );
  const newerVersionId = useMemo(
    () => getText(data!, 'newer_version_id') ?? '',
    [data],
  );
  const originalAvailable = useMemo(
    () => getBoolean(data!, 'original_available') ?? false,
    [data],
  );
  const contentType = useMemo(
    () => getText(data!, 'content_type') ?? 'text',
    [data],
  );

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    scrollDoneRef.current = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Setting initial loading state on mount
    setState('loading');
    setData(null);

    async function load() {
      try {
        const response = await fetchSourceViewer(citation);
        if (cancelled) return;
        setData(response);
        if (response.status === 'not_available') {
          setState('not_available');
        } else {
          setState('success');
        }
      } catch {
        if (cancelled) return;
        setState('error');
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [isOpen, citation]);

  // Scroll to highlight after content renders
  useEffect(() => {
    if (state !== 'success' || !contentRef.current || scrollDoneRef.current) return;

    const highlight = data?.highlight;
    const targetOffset = getScrollTarget(highlight);
    if (targetOffset === null) return;

    // Find the mark element and scroll to it
    const markEl = contentRef.current.querySelector('mark');
    if (markEl && typeof markEl.scrollIntoView === 'function') {
      markEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    scrollDoneRef.current = true;
  }, [state, data?.highlight]);

  const handleOpenOriginal = useCallback(async () => {
    if (!originalAvailable) return;
    setOriginalLoading(true);
    try {
      const response = await fetchOriginalDocument(citation);
      if (response.original_link) {
        window.open(response.original_link, '_blank', 'noopener,noreferrer');
      }
    } catch {
      // ignore
    } finally {
      setOriginalLoading(false);
    }
  }, [citation, originalAvailable]);

  const handleCopyCitation = useCallback(async () => {
    const citationText = [
      `Document: ${documentTitle}`,
      version ? `Version: ${version}` : null,
      page !== undefined && !Number.isNaN(page) ? `Page: ${page}` : null,
      citation.table_id ? `Table: ${citation.table_id}` : null,
      citation.citation_id ? `Citation ID: ${citation.citation_id}` : null,
    ]
      .filter(Boolean)
      .join('\n');

    try {
      await navigator.clipboard.writeText(citationText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  }, [citation, documentTitle, version, page]);

  const handleReportWrongSource = useCallback(async () => {
    try {
      await reportWrongSource({
        document_id: citation.document_id,
        citation_id: citation.citation_id,
        document_title: documentTitle,
        version,
        page,
        table_id: citation.table_id,
      });
      setReported(true);
      setTimeout(() => setReported(false), 3000);
    } catch {
      // ignore
    }
  }, [citation, documentTitle, version, page]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      } else if ((event.key === 'j' || event.key === 'ArrowDown') && hasNext && onNext) {
        event.preventDefault();
        onNext();
      } else if ((event.key === 'k' || event.key === 'ArrowUp') && hasPrevious && onPrevious) {
        event.preventDefault();
        onPrevious();
      }
    },
    [onClose, onNext, onPrevious, hasNext, hasPrevious],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener('keydown', handleKeyDown as EventListener);
    return () => document.removeEventListener('keydown', handleKeyDown as EventListener);
  }, [isOpen, handleKeyDown]);

  const citationLabel = useMemo(() => {
    const parts = [`Citation ${(currentCitationIndex ?? 0) + 1}`];
    if (totalCitations && totalCitations > 1) {
      parts.push(`of ${totalCitations}`);
    }
    return parts.join(' ');
  }, [currentCitationIndex, totalCitations]);

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay for mobile bottom sheet */}
      <div
        className="fixed inset-0 z-40 lg:hidden bg-canvas/40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Overlay for desktop side panel (click outside to close) */}
      <div
        className="fixed inset-0 z-40 hidden lg:block bg-canvas/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        ref={contentRef}
        className={`
          fixed z-50 w-full max-w-xl lg:max-w-lg
          border-l border-line bg-surface shadow-xl
          flex flex-col
          ${isOpen ? 'translate-x-0 translate-y-0' : 'translate-x-full translate-y-full'}
          transition-transform duration-200 ease-out
          lg:relative lg:translate-x-0 lg:translate-y-0 lg:shadow-none lg:border-0 lg:max-w-none lg:flex-1
          /* Mobile: bottom sheet */
          lg:inset-auto inset-x-0 bottom-0 rounded-t-2xl border-t border-l-0
          lg:inset-y-0 lg:right-0 lg:rounded-none lg:border-l lg:border-t-0
        `}
        role="dialog"
        aria-label="Source viewer"
        tabIndex={-1}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line p-4 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <h2 className="text-base font-semibold text-primary truncate">{documentTitle}</h2>
            {version && (
              <span className="inline-flex items-center rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary shrink-0">
                {messages.actions.version} {version}
              </span>
            )}
            {page !== undefined && !Number.isNaN(page) && (
              <span className="inline-flex items-center rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary shrink-0">
                {messages.actions.page} {page}
              </span>
            )}
            {category && (
              <span className="inline-flex items-center rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary shrink-0">
                {category}
              </span>
            )}
            {period && (
              <span className="inline-flex items-center rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary shrink-0">
                {period}
              </span>
            )}
            {documentStatus && (
              <span className="inline-flex items-center rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary shrink-0">
                {documentStatus}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {totalCitations && totalCitations > 1 && (
              <span className="hidden sm:inline-flex items-center gap-1 text-xs text-secondary">
                {citationLabel}
              </span>
            )}
            <Button type="button" variant="ghost" className="h-8 w-8 p-0" onClick={onClose} aria-label={messages.actions.close}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </Button>
          </div>
        </div>

        {/* Newer version banner */}
        {newerVersionAvailable && newerVersionId && onNewerVersion && (
          <InlineNotice tone="info" className="m-4 rounded-md">
            <div className="flex items-center justify-between">
              <span className="text-sm text-primary">
                {messages.sourceViewer.newerVersionAvailable}
              </span>
              <Button type="button" variant="secondary" className="h-8 px-3 text-xs" onClick={onNewerVersion}>
                {messages.sourceViewer.viewNewerVersion}
              </Button>
            </div>
          </InlineNotice>
        )}

        {/* Needs review badge */}
        {needsReview && (
          <InlineNotice tone="warning" className="mx-4 mb-4 rounded-md">
            <span className="text-sm text-primary">{messages.sourceViewer.needsReview}</span>
          </InlineNotice>
        )}

        {/* Content */}
        <div
          className="flex-1 overflow-y-auto p-4 space-y-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          tabIndex={0}
        >
          {isLoading ? (
            <div className="space-y-4" aria-busy="true" aria-live="polite">
              <p className="text-sm text-secondary">{messages.sourceViewer.loading}</p>
              <div className="h-20 animate-pulse rounded-md bg-subtle" />
              <div className="h-20 animate-pulse rounded-md bg-subtle" />
              <div className="h-20 animate-pulse rounded-md bg-subtle" />
            </div>
          ) : isNotAvailable ? (
            <div className="text-center py-8">
              <InlineNotice tone="error">
                <span>{messages.sourceViewer.notAvailable}</span>
              </InlineNotice>
            </div>
          ) : isError ? (
            <div className="text-center py-8">
              <InlineNotice tone="error">
                <span>{messages.sourceViewer.error}</span>
                <div className="mt-2">
                  <Button type="button" variant="secondary" onClick={() => { setState('loading'); }}>
                    {messages.actions.tryAgain}
                  </Button>
                </div>
              </InlineNotice>
            </div>
          ) : data ? (
            <div className="space-y-4">
              {contentType === 'table' && data.table ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-secondary">
                    <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-accent">
                      {messages.sourceViewer.tableContent}
                    </span>
                  </div>
                  {data.tables?.length && data.tables.length > 1 ? (
                    <div className="space-y-4">
                      {data.tables.map((table, index) => {
                        const tables = data.tables!;
                        return (
                          <div key={table.table_id ?? table.id ?? index} className="space-y-2">
                            {tables.length > 1 && (
                              <p className="text-xs font-medium text-secondary">
                                Table {index + 1} {table.table_id ? `(${table.table_id})` : ''}
                              </p>
                            )}
                            {formatTable(table)}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    formatTable(data.table)
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-secondary">
                    <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-accent">
                      {messages.sourceViewer.textContent}
                    </span>
                  </div>
                  <div className="prose prose-sm max-w-none text-primary whitespace-pre-wrap leading-relaxed text-sm leading-relaxed">
                    {highlightText(data.text ?? '', data.highlight ?? null)}
                  </div>
                </div>
              )}

              {data.tables?.length && data.tables.length > 0 && contentType !== 'table' && (
                <details className="group border-t border-line pt-4">
                  <summary className="flex items-center gap-2 cursor-pointer text-sm font-medium text-primary">
                    <span className="rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-secondary">
                      {messages.sourceViewer.tableContent}
                    </span>
                    <svg className="w-4 h-4 text-secondary group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div className="mt-3 space-y-4">
                    {data.tables.map((table, index) => {
                      const tables = data.tables!;
                      return (
                        <div key={table.table_id ?? table.id ?? index} className="space-y-2">
                          {tables.length > 1 && (
                            <p className="text-xs font-medium text-secondary">
                              Table {index + 1} {table.table_id ? `(${table.table_id})` : ''}
                            </p>
                          )}
                          {formatTable(table)}
                        </div>
                      );
                    })}
                  </div>
                </details>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-secondary">
              {messages.sourceViewer.noContent}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-line p-4 flex-shrink-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              className="h-8 px-3 text-xs"
              onClick={handleCopyCitation}
              disabled={copied}
              aria-label={messages.actions.copyCitation}
            >
              {copied ? 'Copied' : messages.actions.copyCitation}
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="h-8 px-3 text-xs"
              onClick={handleReportWrongSource}
              disabled={reported}
              aria-label={messages.actions.reportWrongSource}
            >
              {reported ? 'Reported' : messages.actions.reportWrongSource}
            </Button>
            {originalAvailable && (
              <Button
                type="button"
                variant="primary"
                className="h-8 px-3 text-xs"
                onClick={handleOpenOriginal}
                disabled={originalLoading}
                aria-label={messages.actions.openFullDocument}
              >
                {originalLoading ? 'Loading...' : messages.actions.openFullDocument}
              </Button>
            )}
          </div>

          {/* Navigation for multiple citations */}
          {totalCitations && totalCitations > 1 && (
            <div className="flex items-center justify-between text-xs text-secondary">
              <span>
                {currentCitationIndex !== undefined ? currentCitationIndex + 1 : 1} / {totalCitations}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  className="h-8 px-3 text-xs"
                  onClick={onPrevious}
                  disabled={!hasPrevious}
                  aria-label={messages.actions.previous}
                >
                  {messages.actions.previous}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="h-8 px-3 text-xs"
                  onClick={onNext}
                  disabled={!hasNext}
                  aria-label={messages.actions.next}
                >
                  {messages.actions.next}
                </Button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

export default SourceViewer;
