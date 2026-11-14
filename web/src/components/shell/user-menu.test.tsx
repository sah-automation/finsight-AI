import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { UserMenu } from '@/components/shell/user-menu';

const USER = {
  company_id: 'company-1',
  company_name: 'Acme',
  company_display_name: 'Acme',
  user_id: 'user-1',
  role: 'system_admin',
  role_id: 'system_admin',
  role_name: null,
  permissions: ['manage_settings'],
  permission_actions: ['manage_settings'],
  actions: ['manage_settings'],
  role_actions: ['manage_settings'],
  category_permissions: {},
};

describe('UserMenu', () => {
  it('shows company name and role and offers sign out', () => {
    render(<UserMenu user={USER as never} />);

    expect(screen.getAllByText('Acme').length).toBeGreaterThan(0);
    expect(screen.getAllByText('System Admin').length).toBeGreaterThan(0);
    const form = screen.getByRole('button', { name: 'Sign out' }).closest('form');
    expect(form).toHaveAttribute('action', '/api/auth/sign-out');
    expect(form).toHaveAttribute('method', 'post');
  });
});
