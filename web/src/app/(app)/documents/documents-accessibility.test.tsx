import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { axe } from 'vitest-axe';

import DocumentsLibrary from './documents-library';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/documents',
}));

const USER = {
  company_id: 'company-1',
  company_name: 'Acme',
  company_display_name: 'Acme',
  user_id: 'user-1',
  role: 'audit_compliance',
  permissions: ['read'],
  category_permissions: {},
} as never;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('DocumentsLibrary accessibility', () => {
  beforeEach(() => vi.clearAllMocks());

  it('empty state passes axe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => jsonResponse({ documents: [] })));
    const { container } = render(<DocumentsLibrary user={USER} permissions={['read']} />);
    await waitFor(() => expect(screen.getByText('No documents yet.')).toBeInTheDocument());
    expect((await axe(container)).violations).toEqual([]);
  });

  it('error state passes axe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => jsonResponse({}, 500)));
    const { container } = render(<DocumentsLibrary user={USER} permissions={['read']} />);
    await waitFor(() => expect(screen.getByText('Documents are temporarily unavailable. Please try again.')).toBeInTheDocument());
    expect((await axe(container)).violations).toEqual([]);
  });

  it('loading state passes axe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})));
    const { container } = render(<DocumentsLibrary user={USER} permissions={['read']} />);
    expect(screen.getByText('Loading documents')).toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });

  it('rendered documents pass axe', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
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
    const { container } = render(<DocumentsLibrary user={USER} permissions={['read']} />);
    await waitFor(() => expect(screen.getByText('Budget.xlsx')).toBeInTheDocument());
    expect((await axe(container)).violations).toEqual([]);
  });
});
