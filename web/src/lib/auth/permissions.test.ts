import { describe, expect, it } from 'vitest';

import {
  canAsk,
  canManageSettings,
  canUpload,
  canViewAudit,
  landingPath,
  navigationFor,
} from '@/lib/auth/permissions';

const executive = ['approve', 'read', 'view_original'];
const planner = ['delete', 'read', 'update', 'upload', 'view_original'];
const auditor = ['read', 'view_audit_log', 'view_original'];
const systemAdmin = ['manage_settings', 'manage_users', 'view_audit_log'];

describe('permissions', () => {
  it('builds navigation from permission actions, not role names', () => {
    expect(navigationFor(executive).map((item) => item.id)).toEqual(['ask', 'documents']);
    expect(navigationFor(planner).map((item) => item.id)).toEqual([
      'ask',
      'documents',
      'upload',
    ]);
    expect(navigationFor(systemAdmin).map((item) => item.id)).toEqual(['settings']);
    expect(navigationFor([])).toEqual([]);
  });

  it('keeps audit and executive navigation read-only', () => {
    expect(canUpload(auditor)).toBe(false);
    expect(canManageSettings(auditor)).toBe(false);
    expect(canViewAudit(auditor)).toBe(true);
    expect(canAsk(auditor)).toBe(true);
    expect(canUpload(executive)).toBe(false);
  });

  it('lands executives and planners on Ask and admins on settings', () => {
    expect(landingPath(executive)).toBe('/ask');
    expect(landingPath(planner)).toBe('/ask');
    expect(landingPath(auditor)).toBe('/ask');
    expect(landingPath(systemAdmin)).toBe('/settings');
    expect(landingPath([])).toBe('/permission-denied');
  });
});
