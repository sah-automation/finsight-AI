import createClient from 'openapi-fetch';

import type { paths } from '@/generated/api';

/**
 * Every browser request goes through the authenticated BFF. The client never
 * knows the backend URL and never attaches Cognito tokens.
 */
export const API_BASE_PATH = '/api/backend';

export function createApiClient() {
  return createClient<paths>({
    baseUrl: API_BASE_PATH,
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  });
}

export const api = createApiClient();
