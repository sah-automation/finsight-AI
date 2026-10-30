'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { InlineNotice } from '@/components/ui/inline-notice';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { useRouter } from 'next/navigation';
import type { CurrentUser } from '@/lib/auth/current-user';
import { API_BASE_PATH } from '@/lib/api/client';
import { streamAskQuestion, type AskEvent } from '@/lib/api/events';
import { messages } from '@/lib/messages';

type JsonRecord = Record<string, unknown>;

export interface CitationRecord {
  id?: string | null;
  citation_id?: string | null;
  citationId?: string | null;
  document_id?: string | null;
  documentId?: string | null;
  document_name?: string | null;
  documentName?: string | null;
  document_title?: string | null;
  title?: string | null;
  filename?: string | null;
  version?: string | number | null;
  page?: number | string | null;
  page_number?: number | string | null;
  pageNumber?: number | string | null;
  table_id?: string | null;
  tableId?: string | null;
  table?: string | null;
  excerpt?: string | null;
  snippet?: string | null;
  content?: string | null;
  status?: string | null;
  document_status?: string | null;
  sources?: CitationRecord[] | null;
  calculated?: boolean;
  low_confidence?: boolean;
  needs_review?: boolean;
  currency?: string | null;
  units?: string | null;
  period?: string | null;
  value?: number | string | null;
}

export interface FigureRecord {
  value: number | string;
  currency?: string | null;
  units?: string | null;
  period?: string | null;
  label?: string | null;
  calculated?: boolean;
  needs_review?: boolean;
  low_confidence?: boolean;
}

export interface ThreadMessage {
  id: string;
  role: 'user' | 'assistant';
  question?: string;
  answer?: string;
  status?: string;
  citations: CitationRecord[];
  figures: FigureRecord[];
  busy?: boolean;
  unavailable?: boolean;
  permissionDenied?: boolean;
  insufficientData?: boolean;
  insufficientReason?: string;
  relatedQuestions?: string[];
  cached?: boolean;
  aborted?: boolean;
}

export interface ThreadRecord {
  id?: string | null;
  thread_id?: string | null;
  threadId?: string | null;
  title?: string | null;
  question?: string | null;
  messages?: ThreadMessage[] | null;
}

export interface AskScreenProps {
  user?: CurrentUser;
  permissions?: string[];
  initialThreads?: ThreadRecord[] | null;
  threads?: ThreadRecord[] | null;
  exampleQuestions?: string[] | null;
  example_questions?: string[] | null;
  scopeDocumentCount?: number | string | null;
  scope_document_count?: number | string | null;
  documentCount?: number | string | null;
  document_count?: number | string | null;
  searchedDocumentCount?: number | string | null;
  filters?: string[] | null;
  onOpenSource?: (citation: CitationRecord) => void;
}

function txt(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const result = String(value).trim();
  return result || undefined;
}

function num(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function recordList(value: unknown): JsonRecord[] {
  if (Array.isArray(value)) return value.filter((item): item is JsonRecord => !!item && typeof item === 'object');
  if (value && typeof value === 'object') {
    const record = value as JsonRecord;
    for (const key of ['items', 'threads', 'data', 'results', 'documents']) {
      if (Array.isArray(record[key])) return (record[key] as unknown[]).filter((item): item is JsonRecord => !!item && typeof item === 'object');
    }
  }
  return [];
}

function canAskPermission(permissions: string[] | undefined): boolean {
  const resolved = permissions ?? [];
  return resolved.includes('ask') || resolved.includes('question') || resolved.includes('chat') || resolved.length === 0;
}

export function formatFigure(figure: FigureRecord | JsonRecord): string {
  const rawValue = (figure as FigureRecord).value;
  const parsed = typeof rawValue === 'number' ? rawValue : Number(String(rawValue).replace(/,/g, ''));
  const currency = txt((figure as FigureRecord).currency) ?? 'USD';
  const units = txt((figure as FigureRecord).units) ?? 'units';
  const period = txt((figure as FigureRecord).period) ?? '-';
  if (Number.isFinite(parsed)) {
    const formatted = new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(parsed);
    return `${formatted} ${units}, ${period}`.trim();
  }
  return `${String(rawValue)} ${units}, ${period}`.trim();
}

function formatCitationName(citation: CitationRecord, index: number): string {
  const label = txt(citation.document_name ?? citation.documentName ?? citation.document_title ?? citation.title ?? citation.filename) ?? txt(citation.document_id ?? citation.documentId) ?? `Source ${index + 1}`;
  const parts = [`Source ${index + 1}: ${label}`];
  const page = citation.page ?? citation.page_number ?? citation.pageNumber;
  if (page !== null && page !== undefined) parts.push(`page ${page}`);
  const table = citation.table_id ?? citation.tableId ?? citation.table;
  if (table) parts.push(`table ${table}`);
  if (citation.version !== null && citation.version !== undefined) parts.push(`version ${citation.version}`);
  return parts.join(', ');
}

function citationDocumentName(citation: CitationRecord): string {
  return txt(citation.document_name ?? citation.documentName ?? citation.document_title ?? citation.title ?? citation.filename) ?? txt(citation.document_id ?? citation.documentId) ?? 'Document';
}

function statusMessage(status: string): string {
  const value = status.toLowerCase();
  if (value.includes('wak')) return messages.results.wakingUp;
  if (value.includes('busy')) return messages.results.busy;
  if (value.includes('unavail')) return messages.results.temporarilyUnavailable;
  if (value.includes('number') || value.includes('calc') || value.includes('metric')) return messages.working.numbers;
  if (value.includes('source') || value.includes('verif') || value.includes('citation') || value.includes('evidence')) return messages.working.sources;
  if (value.includes('answer') || value.includes('generat') || value.includes('received')) return messages.working.search;
  return messages.working.search;
}

export function AskScreen({
  user,
  permissions,
  initialThreads,
  threads: threadsProp,
  exampleQuestions,
  example_questions,
  scopeDocumentCount,
  scope_document_count,
  documentCount,
  document_count,
  searchedDocumentCount,
  filters: filtersProp,
  onOpenSource,
}: AskScreenProps) {
  const resolvedPermissions = permissions ?? (user?.permissions ?? user?.permission_actions ?? []);
  const allowed = canAskPermission(resolvedPermissions);

  const [question, setQuestion] = useState('');
  const [messagesList, setMessagesList] = useState<ThreadMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadRecord[]>(() => (initialThreads ?? threadsProp ?? []) as ThreadRecord[]);
  const [filters, setFilters] = useState<string[]>(() => (filtersProp ?? []) as string[]);
  const [filterInput, setFilterInput] = useState('');
  const [selectedCitation, setSelectedCitation] = useState<CitationRecord | null>(null);
  const [copied, setCopied] = useState(false);
  const [showReasons, setShowReasons] = useState(false);
  const [related, setRelated] = useState<string[]>([]);
  const [documentCountState, setDocumentCountState] = useState<number | undefined>(
    num(scopeDocumentCount ?? scope_document_count ?? documentCount ?? document_count ?? searchedDocumentCount) ?? undefined,
  );
  const abortRef = useRef<AbortController | null>(null);
  const firstSentenceRef = useRef(false);

  const router = useRouter();

  const examples = useMemo(() => {
    const passed = exampleQuestions ?? example_questions;
    if (Array.isArray(passed) && passed.length > 0) return passed.map(String);
    const categories = Object.keys(user?.category_permissions ?? {});
    if (categories.length > 0) return categories.slice(0, 3).map((category) => `What changed in ${category}?`);
    return ['What changed quarter over quarter?', 'Which documents support this figure?', 'Are there any open review items?'];
  }, [exampleQuestions, example_questions, user?.category_permissions]);

  useEffect(() => {
    if (documentCountState !== undefined) return;
    let alive = true;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE_PATH}/documents`, { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) return;
        const payload = await response.json().catch(() => null);
        const list = recordList(payload);
        const record = payload && typeof payload === 'object' ? (payload as JsonRecord) : {};
        const count = num(record.total ?? record.count ?? (Array.isArray(record.documents) ? record.documents.length : list.length));
        if (alive && count !== undefined) setDocumentCountState(count);
      } catch {
        // keep unknown
      }
    })();
    return () => { alive = false; };
  }, [documentCountState]);

  const scopeLine = useMemo(() => {
    if (documentCountState !== undefined) return `Searching ${documentCountState} documents, latest versions only`;
    return 'Searching available documents, latest versions only';
  }, [documentCountState]);

  useEffect(() => {
    let alive = true;
    const loadThreads = async () => {
      if (threads.length > 0) return;
      try {
        for (const endpoint of [`${API_BASE_PATH}/chat/threads`, `${API_BASE_PATH}/threads`]) {
          const response = await fetch(endpoint, { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
          if (!response.ok) continue;
          const payload = await response.json().catch(() => null);
          const list = recordList(payload);
          const source = Array.isArray(payload) ? payload : list;
          const normalized = source.map((record) => {
            const candidate = record as JsonRecord;
            return {
              id: String(txt(candidate.id ?? candidate.thread_id ?? candidate.threadId) ?? 'thread'),
              thread_id: txt(candidate.thread_id ?? candidate.threadId ?? candidate.id),
              threadId: txt(candidate.threadId ?? candidate.thread_id ?? candidate.id),
              title: txt(candidate.title ?? candidate.question ?? candidate.name),
              question: txt(candidate.question ?? candidate.query ?? candidate.title ?? candidate.text),
              messages: Array.isArray(candidate.messages) ? (candidate.messages as ThreadMessage[]) : Array.isArray(candidate.history) ? (candidate.history as ThreadMessage[]) : undefined,
            };
          });
          if (alive && normalized.length > 0) {
            setThreads(normalized as ThreadRecord[]);
            return;
          }
        }
      } catch {
        // keep empty
      }
    };
    void loadThreads();
    return () => {
      alive = false;
    };
  }, [threads.length]);

  const updateAssistant = useCallback((updater: (current: ThreadMessage) => ThreadMessage) => {
    setMessagesList((prev) => {
      const next = [...prev];
      const index = next.length - 1;
      if (index >= 0 && next[index]?.role === 'assistant') next[index] = updater(next[index] as ThreadMessage);
      return next;
    });
  }, []);

  const sendMessage = useCallback(async (textToSend: string) => {
    const trimmed = textToSend.trim();
    if (!trimmed || streaming || !allowed) return;
    const userMessage: ThreadMessage = { id: `user-${Date.now()}`, role: 'user', question: trimmed, citations: [], figures: [] };
    const assistantMessage: ThreadMessage = { id: `assistant-${Date.now()}`, role: 'assistant', answer: '', status: messages.working.search, citations: [], figures: [] };
    firstSentenceRef.current = false;
    setMessagesList((prev) => [...prev, userMessage, assistantMessage]);
    setQuestion('');
    setStreaming(true);
    setStatus(messages.working.search);
    setErrorMessage(null);
    setShowReasons(false);
    setRelated([]);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAskQuestion({ question: trimmed, threadId }, {
        signal: controller.signal,
        onEvent: (event: AskEvent) => {
          if (event.type === 'status') {
            const nextStatus = statusMessage((event as { status: string }).status);
            setStatus(nextStatus);
            updateAssistant((current) => ({ ...current, status: nextStatus }));
            return;
          }
          if (event.type === 'delta') {
            if (!firstSentenceRef.current) firstSentenceRef.current = true;
            updateAssistant((current) => ({ ...current, answer: `${current.answer ?? ''}${event.text}`, status: '' }));
            return;
          }
          if (event.type === 'citation') {
            const citation = (event as { citation: CitationRecord }).citation;
            updateAssistant((current) => ({ ...current, citations: [...current.citations, citation] }));
            return;
          }
          if (event.type === 'insufficient_data') {
            const reason = (event as { reason: string }).reason;
            updateAssistant((current) => ({ ...current, insufficientData: true, insufficientReason: reason }));
            return;
          }
          if (event.type === 'complete') {
            const complete = event as { threadId?: string; cached?: boolean; insufficientData?: boolean; relatedQuestions?: string[]; related?: string[] };
            if (complete.threadId) setThreadId(complete.threadId);
            setRelated(complete.relatedQuestions ?? complete.related ?? []);
            updateAssistant((current) => ({
              ...current,
              cached: Boolean(complete.cached),
              status: complete.insufficientData ? current.status : '',
              insufficientData: complete.insufficientData ?? current.insufficientData,
              relatedQuestions: complete.relatedQuestions ?? complete.related ?? current.relatedQuestions,
            }));
            return;
          }
          if (event.type === 'error') {
            const code = (event as { code: string }).code;
            if (code === 'busy') {
              updateAssistant((current) => ({ ...current, busy: true }));
              setErrorMessage(messages.results.busy);
            } else if (code === 'permission_denied') {
              updateAssistant((current) => ({ ...current, permissionDenied: true }));
              setErrorMessage(messages.permission.denied);
            } else {
              updateAssistant((current) => ({ ...current, unavailable: true }));
              setErrorMessage(messages.results.temporarilyUnavailable);
            }
          }
        },
      });
    } catch (error) {
      setErrorMessage(messages.results.temporarilyUnavailable);
      updateAssistant((current) => ({ ...current, unavailable: true }));
      if (error instanceof Error && error.name === 'AbortError') {
        updateAssistant((current) => ({ ...current, aborted: true }));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [allowed, streaming, threadId, updateAssistant]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(question);
    }
  }, [question, sendMessage]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleCopy = useCallback(async () => {
    const lastAssistant = [...messagesList].reverse().find((item) => item.role === 'assistant');
    const answer = lastAssistant?.answer ?? '';
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(answer);
    } catch {
      // ignore
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [messagesList]);

  const handleFeedback = useCallback(async (rating: 'up' | 'down', reason?: string) => {
    try {
      await fetch(`${API_BASE_PATH}/feedback`, {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ rating, reason, thread_id: threadId }),
      });
    } catch {
      // ignore
    }
  }, [threadId]);

  const handleRelatedQuestion = useCallback((value: string) => {
    setQuestion(value);
    void sendMessage(value);
  }, [sendMessage]);

  const handleRetry = useCallback(() => {
    const lastUser = [...messagesList].reverse().find((item) => item.role === 'user');
    if (lastUser?.question) void sendMessage(lastUser.question);
  }, [messagesList, sendMessage]);

  const reopenThread = useCallback(async (thread: ThreadRecord) => {
    const threadIdValue = thread.thread_id ?? thread.threadId ?? thread.id ?? null;
    if (threadIdValue) setThreadId(String(threadIdValue));
    if (Array.isArray(thread.messages) && thread.messages.length > 0) {
      setMessagesList(thread.messages);
      return;
    }
    try {
      for (const endpoint of [`${API_BASE_PATH}/chat/threads/${encodeURIComponent(String(threadIdValue))}`, `${API_BASE_PATH}/threads/${encodeURIComponent(String(threadIdValue))}`]) {
        const response = await fetch(endpoint, { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) continue;
        const payload = await response.json().catch(() => null);
        const record = payload && typeof payload === 'object' ? (payload as JsonRecord) : {};
        const loaded = Array.isArray(record.messages) ? (record.messages as ThreadMessage[]) : Array.isArray(record.history) ? (record.history as ThreadMessage[]) : null;
        if (loaded) {
          setMessagesList(loaded);
          return;
        }
        const questionValue = txt(record.question ?? record.query ?? record.title ?? record.text) ?? thread.question ?? thread.title;
        if (questionValue) setMessagesList([{ id: 'user-reopened', role: 'user', question: questionValue, citations: [], figures: [] }] as ThreadMessage[]);
        return;
      }
    } catch {
      if (thread.question ?? thread.title) setMessagesList([{ id: 'user-reopened', role: 'user', question: (thread.question ?? thread.title) as string, citations: [], figures: [] }] as ThreadMessage[]);
    }
  }, []);

  const openSource = useCallback((citation: CitationRecord) => {
    setSelectedCitation(citation);
    if (onOpenSource) onOpenSource(citation);
  }, [onOpenSource]);

  const lastAssistant = useMemo(() => [...messagesList].reverse().find((item) => item.role === 'assistant'), [messagesList]);
  const isEmptyConversation = messagesList.length === 0;

  if (!allowed) {
    return (
      <div className="space-y-6">
        <PageHeader title={messages.navigation.ask} />
        <EmptyState title={messages.permission.denied} />
      </div>
    );
  }

  const handleFilterKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      const value = filterInput.trim();
      if (value) {
        setFilters((prev) => (prev.includes(value) ? prev : [...prev, value]));
        setFilterInput('');
      }
    }
  };

  const removeFilter = (value: string) => setFilters((prev) => prev.filter((item) => item !== value));

  return (
    <div className="flex gap-6">
      <aside aria-label="Threads" className="hidden w-56 shrink-0 md:block">
        <h2 className="text-sm font-semibold text-primary">Threads</h2>
        <div className="mt-3 space-y-2">
          {threads.length === 0 ? <p className="text-xs text-secondary">No past questions yet.</p> : threads.map((thread) => (
            <button key={String(thread.id ?? thread.thread_id ?? thread.threadId)} type="button" onClick={() => void reopenThread(thread)} className="block w-full rounded-md border border-line px-3 py-2 text-left text-sm text-primary hover:bg-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              {thread.title ?? thread.question ?? 'Question'}
            </button>
          ))}
        </div>
      </aside>

      <div className="min-w-0 flex-1 space-y-6">
        <PageHeader title={messages.navigation.ask} />

        {isEmptyConversation ? (
          <div className="mx-auto max-w-3xl space-y-6 text-center">
            <p className="text-sm text-secondary">{scopeLine}</p>
            <div role="group" aria-label="Example questions" className="flex flex-wrap justify-center gap-2">
              {examples.map((example) => <Button key={example} type="button" variant="secondary" onClick={() => void sendMessage(example)}>{example}</Button>)}
            </div>
            <div className="rounded-lg border border-line bg-surface p-4 text-left">
              <textarea aria-label="Question" placeholder={messages.ask.empty} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} rows={3} className="w-full resize-none border-0 bg-transparent text-base text-primary outline-none" />
              <div className="mt-3 flex justify-end">
                <Button type="button" variant="primary" onClick={() => void sendMessage(question)} disabled={streaming}>Ask</Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {filters.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {filters.map((filter) => (
                  <span key={filter} className="inline-flex items-center gap-1 rounded-full border border-line bg-subtle px-3 py-1 text-xs text-primary">
                    {filter}
                    <button type="button" aria-label={`Remove ${filter}`} onClick={() => removeFilter(filter)} className="text-secondary hover:text-primary">×</button>
                  </span>
                ))}
              </div>
            ) : null}

            <div aria-live="polite" className="space-y-6">
              {messagesList.map((item, index) => {
                if (item.role === 'user') {
                  return <div key={item.id ?? index} className="ml-auto max-w-[80%] rounded-lg bg-subtle px-4 py-2"><p className="text-base text-primary">{item.question}</p></div>;
                }
                const showSkeleton = !item.answer && !item.insufficientData && !item.busy && !item.unavailable && !item.permissionDenied;
                return (
                  <div key={item.id ?? index} className="space-y-4">
                    {item.status || showSkeleton ? (
                      <div className="space-y-2" role="status">
                        {item.status ? <p className="text-sm text-secondary">{item.status}</p> : null}
                        {showSkeleton ? <div className="space-y-2" aria-hidden="true"><div className="h-4 w-3/4 animate-pulse rounded bg-subtle" /><div className="h-4 w-2/3 animate-pulse rounded bg-subtle" /></div> : null}
                      </div>
                    ) : null}

                    {item.permissionDenied ? <InlineNotice tone="error"><span>{messages.permission.denied}</span></InlineNotice> : null}
                    {item.busy ? <InlineNotice tone="info"><span>{messages.results.busy}</span><div className="mt-2"><Button type="button" variant="secondary" onClick={handleRetry}>{messages.actions.tryAgain}</Button></div></InlineNotice> : null}
                    {item.unavailable ? <InlineNotice tone="error"><span>{messages.results.temporarilyUnavailable}</span><div className="mt-2"><Button type="button" variant="secondary" onClick={handleRetry}>{messages.actions.tryAgain}</Button></div></InlineNotice> : null}

                    {item.insufficientData ? (
                      <div className="rounded-lg border border-line bg-surface p-4">
                        <div className="flex items-start gap-3">
                          <span aria-hidden="true" className="text-info">i</span>
                          <div className="space-y-2">
                            <p className="text-base font-medium text-primary">{messages.results.insufficientData}</p>
                            {item.insufficientReason ? <p className="text-sm text-secondary">{item.insufficientReason}</p> : null}
                            <div className="flex gap-2">
                              <Button type="button" variant="secondary" onClick={() => router.push('/upload')}>Upload a document</Button>
                              <Button type="button" variant="secondary" onClick={() => setQuestion(item.question ?? '')}>Rephrase</Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {item.answer ? (
                      <div className="space-y-4">
                        <p className="text-base text-primary whitespace-pre-wrap">{item.answer}</p>

                        {item.citations.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {item.citations.map((citation, citationIndex) => (
                              <CitationChip key={`${citation.id ?? citation.citation_id ?? citationIndex}`} citation={citation} index={citationIndex} onOpen={() => openSource(citation)} />
                            ))}
                          </div>
                        ) : null}

                        {item.citations.length > 0 ? <div className="flex items-center gap-2 text-sm text-secondary"><span aria-hidden="true">📚</span><span>{item.citations.length} sources</span></div> : null}

                        {item.figures.length > 0 ? (
                          <table className="w-full text-sm">
                            <thead><tr><th className="text-left">Figure</th><th className="text-right tabular-nums">Value</th></tr></thead>
                            <tbody>
                              {item.figures.map((figure, figureIndex) => (
                                <tr key={figureIndex}>
                                  <td>{txt(figure.label) ?? `Figure ${figureIndex + 1}`}</td>
                                  <td className="text-right font-variant-numeric tabular-nums">
                                    <span className={Number(figure.value) < 0 ? 'text-negative' : ''}>{formatFigure(figure)}</span>
                                    {figure.calculated ? <span className="ml-2 rounded bg-subtle px-1 text-xs">calculated</span> : null}
                                    {figure.needs_review || figure.low_confidence ? <span className="ml-2 rounded bg-warning-subtle px-1 text-xs text-warning">{messages.results.needsReview}</span> : null}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : null}

                        <div className="flex flex-wrap items-center gap-3 text-sm">
                          <Button type="button" variant="secondary" onClick={() => void handleCopy()}>{copied ? 'Copied' : messages.actions.copy}</Button>
                          <Button type="button" variant="secondary" onClick={() => void handleFeedback('up')} aria-label="Thumbs up">Up</Button>
                          <Button type="button" variant="secondary" onClick={() => setShowReasons(true)} aria-label="Thumbs down">Down</Button>
                          {streaming ? <Button type="button" variant="secondary" onClick={handleStop}>Stop</Button> : null}
                        </div>

                        {showReasons ? (
                          <div className="flex flex-wrap gap-2">
                            {['Wrong numbers', 'Wrong sources', 'Out of date', 'Incomplete'].map((reason) => (
                              <Button key={reason} type="button" variant="secondary" onClick={() => void handleFeedback('down', reason)}>{reason}</Button>
                            ))}
                          </div>
                        ) : null}

                        {item.cached ? <span className="inline-flex rounded-full bg-subtle px-2 py-1 text-xs text-secondary">Cached</span> : null}
                        <p className="text-xs text-secondary">Based on latest final versions</p>

                        {(item.relatedQuestions ?? related).length > 0 ? (
                          <div className="space-y-2">
                            <p className="text-sm font-medium text-primary">Related questions</p>
                            <div className="flex flex-wrap gap-2">
                              {(item.relatedQuestions ?? related).map((relatedQuestion) => <Button key={relatedQuestion} type="button" variant="secondary" onClick={() => handleRelatedQuestion(relatedQuestion)}>{relatedQuestion}</Button>)}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {streaming && status ? <p className="text-sm text-secondary" role="status">{status}</p> : null}
            {errorMessage && !lastAssistant?.answer ? <InlineNotice tone="error"><span>{errorMessage}</span></InlineNotice> : null}

            <div className="sticky bottom-0 rounded-lg border border-line bg-surface p-3">
              <div className="flex gap-2">
                <textarea aria-label="Question" placeholder={messages.ask.empty} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} rows={2} disabled={streaming} className="flex-1 resize-none border-0 bg-transparent text-base text-primary outline-none disabled:opacity-50" />
                <Button type="button" variant="primary" onClick={() => void sendMessage(question)} disabled={streaming || !question.trim()}>Ask</Button>
                {streaming ? <Button type="button" variant="secondary" onClick={handleStop}>Stop</Button> : null}
              </div>
              <div className="mt-2">
                <Input aria-label="Filter" placeholder="Add filter and press Enter" value={filterInput} onChange={(event) => setFilterInput(event.target.value)} onKeyDown={handleFilterKeyDown} />
              </div>
            </div>
          </div>
        )}

        {selectedCitation ? (
          <aside aria-label="Source viewer" className="w-full rounded-lg border border-line bg-surface p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-primary">Source viewer</h3>
              <Button type="button" variant="secondary" onClick={() => setSelectedCitation(null)}>{messages.actions.close}</Button>
            </div>
            <div className="mt-3 space-y-2 text-sm text-primary">
              <p><strong>{citationDocumentName(selectedCitation)}</strong></p>
              {selectedCitation.version !== undefined && selectedCitation.version !== null ? <p>Version {selectedCitation.version}</p> : null}
              {selectedCitation.page !== undefined && selectedCitation.page !== null ? <p>Page {selectedCitation.page}</p> : null}
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}


function CitationChip({ citation, index, onOpen }: { citation: CitationRecord; index: number; onOpen: () => void }) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [sourceIndex, setSourceIndex] = useState(0);
  const name = formatCitationName(citation, index);
  const sources = Array.isArray(citation.sources) && citation.sources.length > 0 ? citation.sources : [citation];
  const activeSource = sources[Math.min(sourceIndex, sources.length - 1)] || citation;
  return (
    <div className="relative inline-block">
      <button
        type="button"
        aria-label={name}
        onMouseEnter={() => setPreviewOpen(true)}
        onMouseLeave={() => setPreviewOpen(false)}
        onFocus={() => setPreviewOpen(true)}
        onBlur={() => setPreviewOpen(false)}
        onClick={onOpen}
        className="inline-flex min-h-6 min-w-6 items-center justify-center rounded bg-accent-subtle px-1 text-xs font-medium text-accent"
      >
        [{index + 1}]
      </button>
      {previewOpen ? (
        <div role="tooltip" className="absolute left-0 z-10 mt-2 w-64 rounded-lg border border-line bg-surface p-3 text-left text-xs text-primary shadow-lg">
          <p className="font-medium">{citationDocumentName(activeSource)}</p>
          {activeSource.version !== undefined && activeSource.version !== null ? <p>Version {activeSource.version}</p> : null}
          {(activeSource.page ?? activeSource.page_number ?? activeSource.pageNumber) !== undefined && (activeSource.page ?? activeSource.page_number ?? activeSource.pageNumber) !== null ? <p>Page {activeSource.page ?? activeSource.page_number ?? activeSource.pageNumber}</p> : null}
          {activeSource.table_id ?? activeSource.tableId ?? activeSource.table ? <p>Table {activeSource.table_id ?? activeSource.tableId ?? activeSource.table}</p> : null}
          {activeSource.status || activeSource.document_status ? <p>{activeSource.status ?? activeSource.document_status}</p> : null}
          {activeSource.excerpt || activeSource.snippet || activeSource.content ? <p className="mt-1 text-secondary">{activeSource.excerpt ?? activeSource.snippet ?? activeSource.content}</p> : null}
          {sources.length > 1 ? (
            <div className="mt-2 flex items-center gap-2">
              <button type="button" onClick={() => setSourceIndex((value) => Math.max(0, value - 1))} aria-label="Previous source">Prev</button>
              <span>{sourceIndex + 1}/{sources.length}</span>
              <button type="button" onClick={() => setSourceIndex((value) => Math.min(sources.length - 1, value + 1))} aria-label="Next source">Next</button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default AskScreen;
export { AskScreen as AskPage };
export { AskScreen as AskPageClient };
export { AskScreen as AskView };
export { AskScreen as AskForm };
export { AskScreen as AskClient };
export { AskScreen as ChatScreen };
export { AskScreen as AskQuestion };
export { formatFigure as formatNumber };
