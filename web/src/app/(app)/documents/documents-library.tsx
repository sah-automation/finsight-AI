'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { InlineNotice } from '@/components/ui/inline-notice';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import type { CurrentUser } from '@/lib/auth/current-user';
import { hasPermission } from '@/lib/auth/permissions';
import { API_BASE_PATH } from '@/lib/api/client';
import { messages } from '@/lib/messages';

type JsonRecord = Record<string, unknown>;

export interface DocumentVersionRecord {
  id?: string | null;
  document_id?: string | null;
  documentId?: string | null;
  version?: string | number | null;
  version_number?: string | number | null;
  state?: string | null;
  status?: string | null;
  ingestion_state?: string | null;
  ingestionState?: string | null;
  lifecycle_state?: string | null;
  page_count?: number | string | null;
  pageCount?: number | string | null;
  pages?: number | string | null;
  filename?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  may_be_affected?: boolean | string | number | null;
  mayBeAffected?: boolean | string | number | null;
  stale?: boolean | string | number | null;
  stale_content?: boolean | string | number | null;
  affected?: boolean | string | number | null;
}

export interface DocumentRecord {
  id?: string | null;
  document_id?: string | null;
  documentId?: string | null;
  filename?: string | null;
  file_name?: string | null;
  name?: string | null;
  title?: string | null;
  category?: string | null;
  document_category?: string | null;
  period?: string | null;
  reporting_period?: string | null;
  status?: string | null;
  state?: string | null;
  ingestion_state?: string | null;
  ingestionState?: string | null;
  lifecycle_state?: string | null;
  page_count?: number | string | null;
  pageCount?: number | string | null;
  pages?: number | string | null;
  uploaded_by?: string | null;
  uploadedBy?: string | null;
  created_at?: string | null;
  createdAt?: string | null;
  updated_at?: string | null;
  updatedAt?: string | null;
  deleted_at?: string | null;
  deletedAt?: string | null;
  may_be_affected?: boolean | string | number | null;
  mayBeAffected?: boolean | string | number | null;
  stale?: boolean | string | number | null;
  stale_content?: boolean | string | number | null;
  affected?: boolean | string | number | null;
  versions?: DocumentVersionRecord[] | null;
  document_versions?: DocumentVersionRecord[] | null;
  version_history?: DocumentVersionRecord[] | null;
  history?: DocumentVersionRecord[] | null;
}

export interface DocumentsLibraryProps {
  user?: CurrentUser;
  permissions?: string[];
  retentionDays?: number | string | null;
  initialDocuments?: DocumentRecord[];
  canUpload?: boolean;
  canDelete?: boolean;
}

function text(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  const result = String(value).trim();
  return result || undefined;
}

function num(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function bool(value: unknown): boolean {
  if (value === true || value === 1) {
    return true;
  }
  if (typeof value === 'string') {
    return value.trim().toLowerCase() === 'true' || value.trim().toLowerCase() === 'yes';
  }
  return false;
}

function date(value: unknown): string {
  const raw = text(value);
  if (!raw) {
    return '';
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(parsed);
}

function idOf(record: unknown): string {
  const candidate =
    record && typeof record === 'object'
      ? (record as Record<string, unknown>)
      : {};
  return String(
    text(
      candidate.id ?? candidate.document_id ?? candidate.documentId,
    ) ?? 'unknown',
  );
}

function ingestionState(record: DocumentRecord | DocumentVersionRecord): string {
  const value = text(
    record.ingestion_state ??
      record.ingestionState ??
      record.state,
  );
  if (!value) {
    return 'received';
  }
  const normalized = value.toLowerCase().replace(/[^a-z]/g, '');
  if (normalized.includes('need') || normalized.includes('review')) {
    return 'needs_review';
  }
  if (normalized.includes('process')) {
    return 'processing';
  }
  if (normalized.includes('commit')) {
    return 'committed';
  }
  if (normalized.includes('ready')) {
    return 'ready';
  }
  if (normalized.includes('store')) {
    return 'stored';
  }
  if (normalized.includes('fail')) {
    return 'failed';
  }
  if (normalized.includes('reject')) {
    return 'rejected';
  }
  if (normalized.includes('supersede')) {
    return 'superseded';
  }
  if (normalized.includes('delete')) {
    return 'deleted';
  }
  return value.toLowerCase().replace(/\s+/g, '_');
}

function ingestionLabel(state: string): string {
  const labels: Record<string, string> = {
    received: 'Received',
    stored: 'Stored',
    processing: 'Processing',
    committed: 'Committed',
    ready: 'Ready',
    needs_review: 'Needs review',
    failed: 'Failed',
    rejected: 'Rejected',
    superseded: 'Superseded',
    deleted: 'Deleted',
  };
  return labels[state] ?? state.replace(/_/g, ' ');
}

function isStaleContent(record: DocumentRecord | DocumentVersionRecord): boolean {
  return (
    bool(record.may_be_affected ?? record.mayBeAffected) ||
    bool(record.stale) ||
    bool(record.stale_content) ||
    bool(record.affected)
  );
}

function normalizeDocument(raw: unknown): DocumentRecord {
  if (raw && typeof raw === 'object') {
    return raw as DocumentRecord;
  }
  return { id: String(raw) };
}

function toList(payload: unknown): DocumentRecord[] {
  if (Array.isArray(payload)) {
    return payload.map(normalizeDocument);
  }
  if (payload && typeof payload === 'object') {
    const record = payload as JsonRecord;
    for (const key of [
      'documents',
      'items',
      'results',
      'records',
      'recycle_bin',
      'deleted_documents',
      'deleted',
    ]) {
      const value = record[key];
      if (Array.isArray(value)) {
        return value.map(normalizeDocument);
      }
    }
    if (record.document && typeof record.document === 'object') {
      return [normalizeDocument(record.document)];
    }
    if (record.data && Array.isArray(record.data)) {
      return record.data.map(normalizeDocument);
    }
  }
  return [];
}

function parseVersions(detail: unknown): DocumentVersionRecord[] {
  if (!detail || typeof detail !== 'object') {
    return [];
  }
  const record = detail as JsonRecord;
  for (const key of ['versions', 'document_versions', 'version_history', 'history', 'items', 'records', 'results']) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value as DocumentVersionRecord[];
    }
  }
  return [];
}

export function DocumentsLibrary({
  user,
  permissions,
  retentionDays,
  initialDocuments,
  canUpload,
  canDelete,
}: DocumentsLibraryProps) {
  const router = useRouter();
  const resolvedPermissions = permissions ?? user?.permissions ?? [];
  const uploadAllowed = canUpload ?? hasPermission(resolvedPermissions, 'upload');
  const deleteAllowed = canDelete ?? hasPermission(resolvedPermissions, 'delete');

  const [view, setView] = useState<'library' | 'recycle'>('library');
  const [documents, setDocuments] = useState<DocumentRecord[]>(initialDocuments ?? []);
  const [loading, setLoading] = useState(!initialDocuments);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [periodFilter, setPeriodFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [ingestionFilter, setIngestionFilter] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'updated' | 'period' | 'category'>('updated');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [detail, setDetail] = useState<DocumentRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    document: DocumentRecord;
    type: 'delete' | 'purge' | 'restore';
  } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadDocuments = useCallback(
    async (targetView: 'library' | 'recycle') => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_PATH}/documents`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            action: targetView === 'recycle' ? 'recycle' : 'list',
            company_id: user?.company_id,
          }),
        });

        if (response.status === 401) {
          throw new Error('session');
        }
        if (!response.ok) {
          throw new Error('request_failed');
        }
        const body = (await response.json().catch(() => null)) as unknown;
        let rows = toList(body);
        if (targetView === 'recycle') {
          rows = rows.filter((item) => Boolean(item.deleted_at ?? item.deletedAt));
        } else {
          rows = rows.filter((item) => !Boolean(item.deleted_at ?? item.deletedAt));
        }
        setDocuments(rows);
      } catch (err) {
        if (err instanceof Error && err.message === 'session') {
          router.replace('/sign-in?reason=expired');
          return;
        }
        setError(messages.documents.error);
      } finally {
        setLoading(false);
      }
    },
    [router, user?.company_id],
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDocuments(view);
  }, [loadDocuments, view]);

  const categories = useMemo(
    () => Array.from(new Set(documents.map((doc) => text(doc.category ?? doc.document_category)).filter(Boolean))) as string[],
    [documents],
  );
  const periods = useMemo(
    () => Array.from(new Set(documents.map((doc) => text(doc.period ?? doc.reporting_period)).filter(Boolean))) as string[],
    [documents],
  );
  const statuses = useMemo(
    () => Array.from(new Set(documents.map((doc) => text(doc.status)).filter(Boolean))) as string[],
    [documents],
  );
  const ingestionStates = useMemo(
    () => Array.from(new Set(documents.map((doc) => ingestionState(doc)))),
    [documents],
  );

  const filteredDocuments = useMemo(() => {
    const needle = query.trim().toLowerCase();
    let result = documents;
    if (needle) {
      result = result.filter((doc) => {
        const name = text(doc.filename ?? doc.file_name ?? doc.name ?? doc.title) ?? '';
        return name.toLowerCase().includes(needle);
      });
    }
    if (categoryFilter) {
      result = result.filter((doc) => text(doc.category ?? doc.document_category) === categoryFilter);
    }
    if (periodFilter) {
      result = result.filter((doc) => text(doc.period ?? doc.reporting_period) === periodFilter);
    }
    if (statusFilter) {
      result = result.filter((doc) => text(doc.status) === statusFilter);
    }
    if (ingestionFilter) {
      result = result.filter((doc) => ingestionState(doc) === ingestionFilter);
    }
    return result;
  }, [categoryFilter, documents, ingestionFilter, periodFilter, query, statusFilter]);

  const sortedDocuments = useMemo(() => {
    const copy = [...filteredDocuments];
    copy.sort((left, right) => {
      const read = (doc: DocumentRecord): string | number => {
        if (sortBy === 'name') {
          return text(doc.filename ?? doc.file_name ?? doc.name ?? doc.title) ?? '';
        }
        if (sortBy === 'period') {
          return text(doc.period ?? doc.reporting_period) ?? '';
        }
        if (sortBy === 'category') {
          return text(doc.category ?? doc.document_category) ?? '';
        }
        return text(doc.updated_at ?? doc.updatedAt ?? doc.created_at ?? doc.createdAt) ?? '';
      };
      const a = read(left);
      const b = read(right);
      const compare = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b));
      return sortDirection === 'asc' ? compare : -compare;
    });
    return copy;
  }, [filteredDocuments, sortBy, sortDirection]);

  const openDetail = useCallback(async (doc: DocumentRecord) => {
    const id = idOf(doc);
    setSelected(doc);
    setDetailLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_PATH}/documents/${encodeURIComponent(id)}${user?.company_id ? `?company_id=${encodeURIComponent(user.company_id)}` : ''}`,
        {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        },
      );
      if (response.ok) {
        const body = (await response.json().catch(() => null)) as unknown;
        if (body && typeof body === 'object' && !Array.isArray(body)) {
          setDetail(normalizeDocument(body));
        } else {
          const rows = toList(body);
          setDetail(rows[0] ?? doc);
        }
      } else {
        setDetail(doc);
      }
    } catch {
      setDetail(doc);
    } finally {
      setDetailLoading(false);
    }
  }, [user?.company_id]);

  const executeMutation = useCallback(
    async (document: DocumentRecord, type: 'delete' | 'purge' | 'restore') => {
      const id = idOf(document);
      try {
        let response: Response;
        if (type === 'delete') {
          response = await fetch(`${API_BASE_PATH}/documents`, {
            method: 'POST',
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
              action: 'delete',
              delete: true,
              document_id: id,
              id,
              company_id: user?.company_id,
            }),
          });
        } else if (type === 'purge') {
          response = await fetch(`${API_BASE_PATH}/documents`, {
            method: 'POST',
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
              action: 'purge',
              purge: true,
              permanent: true,
              document_id: id,
              id,
              company_id: user?.company_id,
            }),
          });
        } else {
          response = await fetch(`${API_BASE_PATH}/documents`, {
            method: 'POST',
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
              action: 'restore',
              restore: true,
              document_id: id,
              id,
              company_id: user?.company_id,
            }),
          });
        }

        if (!response.ok) {
          throw new Error('mutation_failed');
        }
        setDocuments((current) => current.filter((item) => idOf(item) !== id));
        setSelected(null);
        setDetail(null);
        setNotice(
          type === 'delete'
            ? messages.documents.deleteSuccess
            : type === 'purge'
              ? messages.documents.purgeSuccess
              : messages.documents.restoreSuccess,
        );
        await loadDocuments(view);
      } catch {
        setError(messages.documents.error);
      } finally {
        setConfirmAction(null);
      }
    },
    [loadDocuments, view, user?.company_id],
  );

  const toggleSort = (column: 'name' | 'updated' | 'period' | 'category') => {
    if (sortBy === column) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDirection(column === 'name' || column === 'category' ? 'asc' : 'desc');
    }
  };

  const renderIngestionBadge = (state: string) => {
    const label = ingestionLabel(state);
    const tone =
      state === 'failed' || state === 'rejected'
        ? 'bg-negative-subtle text-negative'
        : state === 'needs_review'
          ? 'bg-warning-subtle text-warning'
          : state === 'ready'
            ? 'bg-positive-subtle text-positive'
            : 'bg-subtle text-secondary';
    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
        {label}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={messages.navigation.documents}
        actions={
          uploadAllowed ? (
            <Button type="button" variant="secondary" onClick={() => router.push('/upload')}>
              {messages.documents.upload}
            </Button>
          ) : null
        }
      />

      {notice ? (
        <InlineNotice tone="info">
          <span>{notice}</span>
        </InlineNotice>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[220px] flex-1">
          <Input
            type="search"
            placeholder={messages.documents.searchPlaceholder}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={messages.documents.searchPlaceholder}
          />
        </div>
        <select
          aria-label={messages.documents.category}
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          className="min-h-11 rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
        >
          <option value="">{messages.documents.category}: {messages.documents.all}</option>
          {categories.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          aria-label={messages.documents.period}
          value={periodFilter}
          onChange={(event) => setPeriodFilter(event.target.value)}
          className="min-h-11 rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
        >
          <option value="">{messages.documents.period}: {messages.documents.all}</option>
          {periods.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          aria-label={messages.documents.status}
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="min-h-11 rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
        >
          <option value="">{messages.documents.status}: {messages.documents.all}</option>
          {statuses.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          aria-label={messages.documents.ingestionState}
          value={ingestionFilter}
          onChange={(event) => setIngestionFilter(event.target.value)}
          className="min-h-11 rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
        >
          <option value="">{messages.documents.ingestionState}: {messages.documents.all}</option>
          {ingestionStates.map((item) => (
            <option key={item} value={item}>
              {ingestionLabel(item)}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={view === 'library' ? 'primary' : 'secondary'}
            onClick={() => setView('library')}
          >
            {messages.documents.library}
          </Button>
          <Button
            type="button"
            variant={view === 'recycle' ? 'primary' : 'secondary'}
            onClick={() => setView('recycle')}
          >
            {messages.documents.recycleBin}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={loading}
            onClick={() => void loadDocuments(view)}
          >
            {messages.actions.tryAgain}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3" aria-busy="true" aria-live="polite">
          <p className="text-sm text-secondary">{messages.documents.loading}</p>
          <div className="h-10 animate-pulse rounded-md bg-subtle" />
          <div className="h-10 animate-pulse rounded-md bg-subtle" />
          <div className="h-10 animate-pulse rounded-md bg-subtle" />
        </div>
      ) : null}

      {error && !loading ? (
        <InlineNotice tone="error">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>{error}</span>
            <Button type="button" variant="secondary" onClick={() => void loadDocuments(view)}>
              {messages.actions.tryAgain}
            </Button>
          </div>
        </InlineNotice>
      ) : null}

      {!loading && !error && documents.length === 0 ? (
        <EmptyState
          title={messages.documents.empty}
          action={
            uploadAllowed ? (
              <Button type="button" variant="primary" onClick={() => router.push('/upload')}>
                {messages.documents.upload}
              </Button>
            ) : null
          }
        />
      ) : null}

      {!loading && !error && documents.length > 0 && sortedDocuments.length === 0 ? (
        <EmptyState
          title={messages.documents.filterNoResults}
          action={
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setQuery('');
                setCategoryFilter('');
                setPeriodFilter('');
                setStatusFilter('');
                setIngestionFilter('');
              }}
            >
              {messages.documents.clearFilters}
            </Button>
          }
        />
      ) : null}

      {!loading && !error && sortedDocuments.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="min-w-full border-collapse text-sm">
            <thead className="bg-subtle text-left text-xs font-medium uppercase tracking-wide text-secondary">
              <tr>
                <th
                  className="px-4 py-3"
                  aria-sort={
                    sortBy === 'name'
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  <button
                    type="button"
                    onClick={() => toggleSort('name')}
                    className="font-medium"
                  >
                    {messages.documents.name}
                  </button>
                </th>
                <th
                  className="px-4 py-3"
                  aria-sort={
                    sortBy === 'category'
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  <button
                    type="button"
                    onClick={() => toggleSort('category')}
                    className="font-medium"
                  >
                    {messages.documents.category}
                  </button>
                </th>
                <th
                  className="px-4 py-3"
                  aria-sort={
                    sortBy === 'period'
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  <button
                    type="button"
                    onClick={() => toggleSort('period')}
                    className="font-medium"
                  >
                    {messages.documents.period}
                  </button>
                </th>
                <th className="px-4 py-3">{messages.documents.status}</th>
                <th className="px-4 py-3">{messages.documents.ingestionState}</th>
                <th className="px-4 py-3">{messages.documents.pageCount}</th>
                <th
                  className="px-4 py-3"
                  aria-sort={
                    sortBy === 'updated'
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  <button
                    type="button"
                    onClick={() => toggleSort('updated')}
                    className="font-medium"
                  >
                    {messages.documents.updated}
                  </button>
                </th>
                <th className="px-4 py-3">{messages.documents.uploadedBy}</th>
              </tr>
            </thead>
            <tbody>
              {sortedDocuments.map((doc) => {
                const id = idOf(doc);
                const stale = isStaleContent(doc);
                const state = ingestionState(doc);
                return (
                  <tr
                    key={id}
                    tabIndex={0}
                    onClick={() => void openDetail(doc)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        void openDetail(doc);
                      }
                    }}
                    className="cursor-pointer border-t border-line hover:bg-subtle focus-visible:bg-subtle"
                  >
                    <td className="px-4 py-3 font-medium text-primary">
                      <div className="flex items-center gap-2">
                        <span>{text(doc.filename ?? doc.file_name ?? doc.name ?? doc.title) ?? messages.documents.untitled}</span>
                        {stale ? (
                          <span className="rounded-full bg-warning-subtle px-2 py-0.5 text-xs font-medium text-warning">
                            {messages.documents.staleContent}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-secondary">{text(doc.category ?? doc.document_category) ?? messages.documents.notAvailable}</td>
                    <td className="px-4 py-3 text-secondary">{text(doc.period ?? doc.reporting_period) ?? messages.documents.notAvailable}</td>
                    <td className="px-4 py-3 text-secondary">{text(doc.status) ?? messages.documents.notAvailable}</td>
                    <td className="px-4 py-3">{renderIngestionBadge(state)}</td>
                    <td className="px-4 py-3 text-secondary tabular-nums">{num(doc.page_count ?? doc.pageCount ?? doc.pages) ?? messages.documents.notAvailable}</td>
                    <td className="px-4 py-3 text-secondary">{date(doc.updated_at ?? doc.updatedAt ?? doc.created_at ?? doc.createdAt)}</td>
                    <td className="px-4 py-3 text-secondary">{text(doc.uploaded_by ?? doc.uploadedBy) ?? messages.documents.notAvailable}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {selected ? (
        <div
          className="fixed inset-0 z-40 flex justify-end bg-canvas/40"
          role="dialog"
          aria-label={messages.documents.detailTitle}
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setSelected(null);
              setDetail(null);
            }
          }}
        >
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-line bg-surface p-6 shadow-lg">
            <div className="mb-4 flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold text-primary">{messages.documents.detailTitle}</h2>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSelected(null);
                  setDetail(null);
                }}
              >
                {messages.documents.closeDetail}
              </Button>
            </div>

            {detailLoading ? <p className="text-sm text-secondary">{messages.documents.loading}</p> : null}

            {!detailLoading && (detail ?? selected) ? (
              <div className="space-y-4">
                {(() => {
                  const doc = detail ?? selected!;
                  return (
                    <>
                      <h3 className="text-base font-semibold text-primary">
                        {text(doc.filename ?? doc.file_name ?? doc.name ?? doc.title) ?? messages.documents.untitled}
                      </h3>
                      {isStaleContent(doc) ? (
                        <InlineNotice tone="warning">
                          <span>{messages.documents.staleContent}</span>
                        </InlineNotice>
                      ) : null}
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <dt className="text-secondary">{messages.documents.category}</dt>
                          <dd className="font-medium text-primary">{text(doc.category ?? doc.document_category) ?? messages.documents.notAvailable}</dd>
                        </div>
                        <div>
                          <dt className="text-secondary">{messages.documents.period}</dt>
                          <dd className="font-medium text-primary">{text(doc.period ?? doc.reporting_period) ?? messages.documents.notAvailable}</dd>
                        </div>
                        <div>
                          <dt className="text-secondary">{messages.documents.status}</dt>
                          <dd className="font-medium text-primary">{text(doc.status) ?? messages.documents.notAvailable}</dd>
                        </div>
                        <div>
                          <dt className="text-secondary">{messages.documents.ingestionState}</dt>
                          <dd className="font-medium text-primary">{ingestionLabel(ingestionState(doc))}</dd>
                        </div>
                        <div>
                          <dt className="text-secondary">{messages.documents.pageCount}</dt>
                          <dd className="font-medium text-primary tabular-nums">
                            {num(doc.page_count ?? doc.pageCount ?? doc.pages) ?? messages.documents.notAvailable}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-secondary">{messages.documents.updated}</dt>
                          <dd className="font-medium text-primary">{date(doc.updated_at ?? doc.updatedAt ?? doc.created_at ?? doc.createdAt)}</dd>
                        </div>
                      </dl>

                      <div>
                        <h4 className="text-sm font-semibold text-primary">{messages.documents.versions}</h4>
                        <ul className="mt-2 space-y-2">
                          {parseVersions(detail ?? selected).length === 0 ? (
                            <li className="text-sm text-secondary">{messages.documents.empty}</li>
                          ) : (
                            parseVersions(detail ?? selected).map((version, index) => (
                              <li
                                key={String(version.id ?? index)}
                                className="rounded-md border border-line bg-subtle p-3 text-sm"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <span className="font-medium text-primary">
                                    {messages.documents.version}{' '}
                                    {text(version.version ?? version.version_number) ?? index + 1}
                                  </span>
                                  {renderIngestionBadge(ingestionState(version as DocumentRecord))}
                                </div>
                                <div className="mt-1 text-secondary">
                                  {date(version.created_at ?? version.updated_at)}
                                  {num(version.page_count ?? version.pages) ? ` · ${num(version.page_count ?? version.pages)} ${messages.documents.pageCount}` : ''}
                                </div>
                                {isStaleContent(version as DocumentRecord) ? (
                                  <div className="mt-2 text-warning">{messages.documents.staleContent}</div>
                                ) : null}
                              </li>
                            ))
                          )}
                        </ul>
                      </div>

                      {uploadAllowed || deleteAllowed ? (
                        <div className="flex flex-wrap gap-2 pt-2">
                          {view === 'recycle' && deleteAllowed ? (
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() =>
                                setConfirmAction({ document: doc, type: 'restore' })
                              }
                            >
                              {messages.documents.restore}
                            </Button>
                          ) : null}
                          {view !== 'recycle' && deleteAllowed ? (
                            <Button
                              type="button"
                              variant="destructive"
                              onClick={() =>
                                setConfirmAction({ document: doc, type: 'delete' })
                              }
                            >
                              {messages.documents.delete}
                            </Button>
                          ) : null}
                          {view === 'recycle' && deleteAllowed ? (
                            <Button
                              type="button"
                              variant="destructive"
                              onClick={() =>
                                setConfirmAction({ document: doc, type: 'purge' })
                              }
                            >
                              {messages.documents.purge}
                            </Button>
                          ) : null}
                        </div>
                      ) : null}
                    </>
                  );
                })()}
              </div>
            ) : null}
          </aside>
        </div>
      ) : null}

      {confirmAction ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setConfirmAction(null);
            }
          }}
        >
          <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6 shadow-xl">
            <h3 className="text-base font-semibold text-primary">
              {confirmAction.type === 'purge'
                ? messages.documents.purge
                : confirmAction.type === 'restore'
                  ? messages.documents.restore
                  : messages.documents.delete}
            </h3>
            <p className="mt-2 text-sm text-secondary">
              {confirmAction.type === 'delete'
                ? retentionDays
                  ? `${messages.documents.deleteConfirm} ${messages.documents.restoreWithin}`
                  : messages.documents.deleteConfirm
                : confirmAction.type === 'purge'
                  ? messages.documents.purgeConfirm
                  : messages.documents.restoreSuccess}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setConfirmAction(null)}>
                {messages.actions.close}
              </Button>
              <Button
                type="button"
                variant={confirmAction.type === 'purge' ? 'destructive' : 'primary'}
                onClick={() =>
                  void executeMutation(confirmAction.document, confirmAction.type)
                }
              >
                {confirmAction.type === 'delete'
                  ? messages.documents.delete
                  : confirmAction.type === 'purge'
                    ? messages.documents.purge
                    : messages.documents.restore}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default DocumentsLibrary;

// Compatibility aliases for page/route and test imports.
export const DocumentsPageClient = DocumentsLibrary;
export const DocumentsScreen = DocumentsLibrary;
export const DocumentLibrary = DocumentsLibrary;
