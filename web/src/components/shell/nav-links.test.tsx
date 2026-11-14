import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NavLinks } from '@/components/shell/nav-links';

vi.mock('next/navigation', () => ({
  usePathname: () => '/ask',
}));

describe('NavLinks', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders only navigation the user may access', () => {
    render(<NavLinks permissions={['approve', 'read', 'view_original']} />);

    expect(screen.getByRole('link', { name: 'Ask' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Documents' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Upload' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument();
  });

  it('marks the current route as the current page', () => {
    render(<NavLinks permissions={['read']} />);
    expect(screen.getByRole('link', { name: 'Ask' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('shows a permission message when nothing is accessible', () => {
    render(<NavLinks permissions={[]} />);
    expect(screen.getByText("You don't have access to this.")).toBeInTheDocument();
  });
});
