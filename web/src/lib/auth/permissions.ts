/**
 * Permission-derived navigation and page access.
 *
 * Components and route guards call these helpers. They never branch on a role
 * name. The permission list always comes from the backend current-user
 * endpoint, which reads `config/permissions.yaml`.
 */

export type PermissionAction =
  | 'read'
  | 'upload'
  | 'update'
  | 'delete'
  | 'view_original'
  | 'approve'
  | 'manage_users'
  | 'manage_settings'
  | 'view_audit_log';

export type NavigationId = 'ask' | 'documents' | 'upload' | 'settings';

export interface NavigationItem {
  id: NavigationId;
  href: string;
  requiredAction: PermissionAction | readonly PermissionAction[];
}

const navigation: readonly NavigationItem[] = [
  { id: 'ask', href: '/ask', requiredAction: 'read' },
  { id: 'documents', href: '/documents', requiredAction: 'read' },
  { id: 'upload', href: '/upload', requiredAction: 'upload' },
  {
    id: 'settings',
    href: '/settings',
    requiredAction: ['manage_settings', 'manage_users'],
  },
];

export function hasPermission(
  permissions: readonly string[],
  action: PermissionAction | readonly PermissionAction[],
): boolean {
  const required = typeof action === 'string' ? [action] : action;
  return required.some((candidate) => permissions.includes(candidate));
}

export function canAsk(permissions: readonly string[]): boolean {
  return hasPermission(permissions, 'read');
}

export function canViewDocuments(permissions: readonly string[]): boolean {
  return hasPermission(permissions, 'read');
}

export function canUpload(permissions: readonly string[]): boolean {
  return hasPermission(permissions, 'upload');
}

export function canManageSettings(permissions: readonly string[]): boolean {
  return hasPermission(permissions, ['manage_settings', 'manage_users']);
}

export function canViewAudit(permissions: readonly string[]): boolean {
  return hasPermission(permissions, 'view_audit_log');
}

export function navigationFor(permissions: readonly string[]): NavigationItem[] {
  return navigation.filter((item) => hasPermission(permissions, item.requiredAction));
}

/**
 * Executives and planners land on Ask. Roles that cannot read financial
 * content land on the first permitted administrative screen.
 */
export function landingPath(permissions: readonly string[]): string {
  if (canAsk(permissions)) {
    return '/ask';
  }
  if (canManageSettings(permissions)) {
    return '/settings';
  }
  if (canViewDocuments(permissions)) {
    return '/documents';
  }
  return '/permission-denied';
}
