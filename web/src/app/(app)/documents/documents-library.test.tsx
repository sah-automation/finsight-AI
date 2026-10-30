import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import DocumentsLibrary from './documents-library';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/documents',
}));

const USER = {
  company_id: 'company-1',
  company_name: 'Acme',
  company_display_name: 'Acme',
  user_id: 'user-1',
  role: 'audit_compliance',
  role_id: 'audit_compliance',
  role_name: 'Audit & Compliance',
  permissions: ['read'],
  permission_actions: ['read'],
  actions: ['read'],
  role_actions: [],
  category_permissions: {},
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('DocumentsLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading then empty state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ documents: [] })),
    );
    render(<DocumentsLibrary user={USER as never} permissions={['read']} />);
    expect(screen.getByText('Loading documents')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('No documents yet.')).toBeInTheDocument());
  });

  it('renders documents and details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          documents: [
            {
              id: 'doc-1',
              filename: 'Budget.xlsx',
              category: 'Budget',
              period: '2025-FY',
              status: 'committed',
              state: 'ready',
              page_count: 4,
              updated_at: '2026-01-01T00:00:00Z',
              uploaded_by: 'alice',
            },
          ],
        }),
      ),
    );
    render(<DocumentsLibrary user={USER as never} permissions={['read', 'delete']} />);
    await waitFor(() => expect(screen.getByText('Budget.xlsx')).toBeInTheDocument());
    expect(screen.getByText('Ready', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('shows error state on failed fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 500)));
    render(<DocumentsLibrary user={USER as never} permissions={['read']} />);
    await waitFor(() =>
      expect(screen.getByText('Documents are temporarily unavailable. Please try again.')).toBeInTheDocument(),
    );
  });

  it('audit users do not see delete controls', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          documents: [
            {
              id: 'doc-1',
              filename: 'Budget.xlsx',
              category: 'Budget',
              period: '2025-FY',
              status: 'committed',
              state: 'ready',
            },
          ],
        }),
      ),
    );
    render(<DocumentsLibrary user={USER as never} permissions={['read']} />);
    await waitFor(() => expect(screen.getByText('Budget.xlsx')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upload document' })).not.toBeInTheDocument();
  });
});
