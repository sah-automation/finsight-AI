import 'server-only';

import type { CurrentUser, CurrentUserClient } from '@/lib/auth/current-user';
import { BackendUnavailableError } from '@/lib/auth/types';

/**
 * Mock current user client for local development.
 * Extracts user info from mock tokens instead of calling backend.
 * ONLY use in development - never in production.
 */
export class MockCurrentUserClient implements CurrentUserClient {
  private readonly users = new Map<string, CurrentUser>([
    ['admin@testcompany.com', {
      company_id: 'aacd404c-30bf-49ec-8675-985b1c308a2e',
      company_name: 'Test Company',
      company_display_name: 'Test Company',
      role: 'corporate_finance_planners',
      role_id: 'corporate_finance_planners',
      permissions: ['read', 'upload', 'update', 'delete', 'view_original', 'approve', 'manage_users', 'manage_settings', 'view_audit_log'],
      category_permissions: {
        invoice: ['read', 'upload', 'update', 'delete', 'view_original'],
        bank_statement: ['read', 'upload', 'update', 'delete', 'view_original'],
        financial_statement: ['read', 'upload', 'update', 'delete', 'view_original'],
        budget: ['read', 'upload', 'update', 'delete', 'view_original'],
        contract: ['read', 'upload', 'update', 'delete', 'view_original'],
        board_report: ['read', 'upload', 'update', 'delete', 'view_original'],
      },
    }],
    ['user@testcompany.com', {
      company_id: 'aacd404c-30bf-49ec-8675-985b1c308a2e',
      company_name: 'Test Company',
      company_display_name: 'Test Company',
      role: 'corporate_finance_planners',
      role_id: 'corporate_finance_planners',
      permissions: ['read', 'upload'],
      category_permissions: {
        invoice: ['read', 'upload'],
        bank_statement: ['read', 'upload'],
      },
    }],
  ]);

  addUser(email: string, user: CurrentUser): void {
    this.users.set(email.toLowerCase(), user);
  }

  async fetch(accessToken: string): Promise<CurrentUser> {
    // Extract email from mock token: "mock-access-token-email@domain.com-timestamp"
    const match = accessToken.match(/^mock-access-token-(.+)-\d+$/);
    if (!match) {
      throw new BackendUnavailableError('Invalid mock access token');
    }
    const email = (match[1] ?? '').toLowerCase();
    const user = this.users.get(email);
    if (!user) {
      throw new BackendUnavailableError(`User not found: ${email}`);
    }
    return user;
  }
}

/**
 * Singleton for development use.
 * In production, this should never be used.
 */
let devMockClient: MockCurrentUserClient | null = null;

export function getDevMockCurrentUserClient(): MockCurrentUserClient {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('MockCurrentUserClient must not be used in production');
  }
  devMockClient ??= new MockCurrentUserClient();
  return devMockClient;
}

export function resetDevMockCurrentUserClientForTests(): void {
  devMockClient = null;
}
