import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { AppShell } from '@/components/shell/app-shell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/settings',
}));

describe('AppShell accessibility', () => {
  it('passes axe checks', async () => {
    const USER = {
      company_id: 'company-1',
      company_name: 'Acme',
      company_display_name: 'Acme',
      user_id: 'user-1',
      role: 'system_admin',
      role_id: 'system_admin',
      role_name: 'System Admin',
      permissions: ['manage_settings'],
      permission_actions: ['manage_settings'],
      actions: ['manage_settings'],
      role_actions: ['manage_settings'],
      category_permissions: {},
    };

    const { container } = render(
      <AppShell user={USER as never}>
        <h1>Settings</h1>
      </AppShell>,
    );

    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
