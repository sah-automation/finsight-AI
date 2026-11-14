import 'server-only';

import type { components } from '@/generated/api';
import { BackendUnavailableError } from '@/lib/auth/types';

export type CurrentUser = components['schemas']['CurrentUser'];

export interface CurrentUserClient {
  fetch(accessToken: string): Promise<CurrentUser>;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function parseCurrentUser(value: unknown): CurrentUser {
  if (!value || typeof value !== 'object') {
    throw new BackendUnavailableError('Invalid current-user response');
  }
  const user = value as Record<string, unknown>;
  const categoryPermissions = user.category_permissions ?? {};
  const validCategories =
    categoryPermissions !== null &&
    typeof categoryPermissions === 'object' &&
    Object.values(categoryPermissions).every(isStringArray);

  if (
    typeof user.company_id !== 'string' ||
    !user.company_id ||
    typeof user.company_name !== 'string' ||
    !user.company_name ||
    typeof user.role !== 'string' ||
    !user.role ||
    !isStringArray(user.permissions) ||
    !validCategories
  ) {
    throw new BackendUnavailableError('Incomplete current-user response');
  }
  return user as CurrentUser;
}

export interface BackendCurrentUserClientOptions {
  backendApiUrl: string;
  timeoutMs: number;
  fetchImpl?: typeof fetch;
}

export class BackendCurrentUserClient implements CurrentUserClient {
  private readonly options: BackendCurrentUserClientOptions;

  constructor(options: BackendCurrentUserClientOptions) {
    this.options = options;
  }

  async fetch(accessToken: string): Promise<CurrentUser> {
    const fetchImpl = this.options.fetchImpl ?? fetch;
    let response: Response;
    try {
      response = await fetchImpl(`${this.options.backendApiUrl}/me`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        cache: 'no-store',
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });
    } catch {
      throw new BackendUnavailableError('Current-user request failed');
    }

    if (!response.ok) {
      throw new BackendUnavailableError(`Current-user request returned ${response.status}`);
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new BackendUnavailableError('Current-user response was not JSON');
    }
    return parseCurrentUser(payload);
  }
}
