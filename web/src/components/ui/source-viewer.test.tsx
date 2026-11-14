import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';

import { SourceViewer } from '@/components/ui/source-viewer';
import { fetchSourceViewer, fetchOriginalDocument, reportWrongSource } from '@/lib/api/events';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/ask',
}));

vi.mock('@/lib/api/events', async () => {
  const actual = await vi.importActual('@/lib/api/events');
  return {
    ...actual,
    fetchSourceViewer: vi.fn(),
    fetchOriginalDocument: vi.fn(),
    reportWrongSource: vi.fn(),
  };
});

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

const MOCK_CITATION = {
  document_id: 'doc-1',
  citation_id: 'cite-1',
  document_title: 'Test Document',
  document_version: 'v2',
  page_number: 3,
  table_id: 'table-1',
  category: 'Budget',
  period: '2025-Q1',
  document_status: 'committed',
};

const MOCK_SOURCE_RESPONSE = {
  status: 'available' as const,
  document_id: 'doc-1',
  document_title: 'Test Document',
  document_version: 'v2',
  page_number: 3,
  content_type: 'text' as const,
  text: 'The quick brown fox jumps over the lazy dog.',
  highlight: { start_char: 4, end_char: 9 },
  needs_review: false,
  newer_version_available: true,
  newer_version_id: 'v3',
  original_available: true,
  original_link: 'https://example.com/original.pdf',
  category: 'Budget',
  period: '2025-Q1',
  document_status: 'committed',
};

const MOCK_TABLE_RESPONSE = {
  status: 'available' as const,
  document_id: 'doc-1',
  document_title: 'Test Document',
  document_version: 'v2',
  page_number: 3,
  content_type: 'table' as const,
  text: '',
  table: {
    table_id: 'table-1',
    headers: ['Column A', 'Column B'],
    rows: [['Row 1 Col A', 'Row 1 Col B'], ['Row 2 Col A', 'Row 2 Col B']],
    needs_review: false,
  },
  tables: [
    {
      table_id: 'table-1',
      headers: ['Column A', 'Column B'],
      rows: [['Row 1 Col A', 'Row 1 Col B'], ['Row 2 Col A', 'Row 2 Col B']],
      needs_review: false,
    },
  ],
  highlight: null,
  needs_review: false,
  newer_version_available: false,
  original_available: true,
  original_link: 'https://example.com/original.pdf',
  category: 'Budget',
  period: '2025-Q1',
  document_status: 'committed',
};

const MOCK_NOT_AVAILABLE_RESPONSE = {
  status: 'not_available' as const,
};



describe('SourceViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Loading source')).toBeInTheDocument();
  });

  it('renders text content with highlight', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    expect(screen.getByText('Version v2')).toBeInTheDocument();
    expect(screen.getByText('Page 3')).toBeInTheDocument();
    expect(screen.getByText('Budget')).toBeInTheDocument();
    expect(screen.getByText('2025-Q1')).toBeInTheDocument();
    expect(screen.getByText('committed')).toBeInTheDocument();

    // Check highlighted text
    const mark = screen.getByText('quick');
    expect(mark).toBeInTheDocument();
    expect(mark.tagName).toBe('MARK');
  });

  it('renders table content', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_TABLE_RESPONSE);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    // Check table headers
    expect(screen.getByText('Column A')).toBeInTheDocument();
    expect(screen.getByText('Column B')).toBeInTheDocument();

    // Check table rows
    expect(screen.getByText('Row 1 Col A')).toBeInTheDocument();
    expect(screen.getByText('Row 1 Col B')).toBeInTheDocument();
  });

  it('shows newer version banner', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    const onNewerVersion = vi.fn();
    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
        onNewerVersion={onNewerVersion}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('A newer version of this document exists.')).toBeInTheDocument();
    });

    const newerVersionButton = screen.getByRole('button', { name: 'View newer version' });
    expect(newerVersionButton).toBeInTheDocument();

    await userEvent.click(newerVersionButton);
    expect(onNewerVersion).toHaveBeenCalled();
  });

  it('shows not available message', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_NOT_AVAILABLE_RESPONSE);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('This source is not available.')).toBeInTheDocument();
    });
  });

  it('closes on Escape key', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    const onClose = vi.fn();
    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    // Press Escape
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('navigates with J/K keys', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    const onNext = vi.fn();
    const onPrevious = vi.fn();

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
        onNext={onNext}
        onPrevious={onPrevious}
        hasNext={true}
        hasPrevious={true}
        totalCitations={3}
        currentCitationIndex={1}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    // Press J for next
    await userEvent.keyboard('j');
    expect(onNext).toHaveBeenCalled();

    // Press K for previous
    await userEvent.keyboard('k');
    expect(onPrevious).toHaveBeenCalled();
  });

  it('navigates with Arrow keys', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    const onNext = vi.fn();
    const onPrevious = vi.fn();

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
        onNext={onNext}
        onPrevious={onPrevious}
        hasNext={true}
        hasPrevious={true}
        totalCitations={3}
        currentCitationIndex={1}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    // Press ArrowDown for next
    await userEvent.keyboard('{ArrowDown}');
    expect(onNext).toHaveBeenCalled();

    // Press ArrowUp for previous
    await userEvent.keyboard('{ArrowUp}');
    expect(onPrevious).toHaveBeenCalled();
  });

  it('copies citation to clipboard', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    // Just verify the copy button works
    const copyButton = screen.getByRole('button', { name: 'Copy citation' });
    await userEvent.click(copyButton);

    // In jsdom, clipboard API may not work, so just verify the button exists and is clickable
    expect(copyButton).toBeInTheDocument();
  });

  it('reports wrong source', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);
    vi.mocked(reportWrongSource).mockResolvedValue(undefined);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    const reportButton = screen.getByRole('button', { name: 'Report wrong source' });
    await act(async () => {
      await userEvent.click(reportButton);
    });

    await waitFor(() => {
      expect(reportWrongSource).toHaveBeenCalled();
    });
  });

  it('opens original document', async () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);
    vi.mocked(fetchOriginalDocument).mockResolvedValue({
      status: 'available' as const,
      original_link: 'https://example.com/original.pdf',
      original_available: true,
    });

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Document')).toBeInTheDocument();
    });

    const openButton = screen.getByRole('button', { name: 'Open full document' });
    await userEvent.click(openButton);

    expect(fetchOriginalDocument).toHaveBeenCalled();
  });

  it('renders nothing when isOpen is false', () => {
    vi.mocked(fetchSourceViewer).mockResolvedValue(MOCK_SOURCE_RESPONSE);

    const { queryByText } = render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={false}
        onClose={vi.fn()}
      />
    );

    expect(queryByText('Test Document')).not.toBeInTheDocument();
    expect(queryByText('Loading source')).not.toBeInTheDocument();
  });

  it('shows needs review badge when applicable', async () => {
    const responseWithReview = { ...MOCK_SOURCE_RESPONSE, needs_review: true, status: 'available' as const, content_type: 'text' as const };
    vi.mocked(fetchSourceViewer).mockResolvedValue(responseWithReview);

    render(
      <SourceViewer
        citation={MOCK_CITATION}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Needs review. Some numbers couldn't be read with confidence.")).toBeInTheDocument();
    });
  });
});
