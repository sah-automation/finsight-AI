import { describe, expect, it, vi } from 'vitest';

import { BackendCurrentUserClient } from '@/lib/auth/current-user';
import { BackendUnavailableError } from '@/lib/auth/types';

const valid = {
  company_id: 'company-1',
  company_name: 'Acme',
  company_display_name: 'Acme',
  role: 'executive_leadership',
  role_id: 'executive_leadership',
  role_name: 'Executive Leadership',
  permissions: ['read'],
  category_permissions: { invoice: ['read'] },
};

function client(fetchImpl: typeof fetch) {
  return new BackendCurrentUserClient({
    backendApiUrl: 'https://api.example.com',
    timeoutMs: 1_000,
    fetchImpl,
  });
}

describe('BackendCurrentUserClient', () => {
  it('attaches the access token and validates the response', async () => {
    const fetchImpl = vi.fn(async () => Response.json(valid));
    const user = await client(fetchImpl as typeof fetch).fetch('access-token');

    expect(user).toMatchObject({ company_name: 'Acme', role_id: 'executive_leadership' });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.example.com/me');
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer access-token');
    expect(init.cache).toBe('no-store');
  });

  it('rejects incomplete current-user responses', async () => {
    const fetchImpl = vi.fn(async () => Response.json({ ...valid, company_name: '' }));
    await expect(client(fetchImpl as typeof fetch).fetch('token')).rejects.toBeInstanceOf(
      BackendUnavailableError,
    );
  });

  it('rejects non-JSON and non-OK responses', async () => {
    const html = vi.fn(async () => new Response('<html></html>', { status: 200 }));
    await expect(client(html as typeof fetch).fetch('token')).rejects.toBeInstanceOf(
      BackendUnavailableError,
    );

    const forbidden = vi.fn(async () => new Response(null, { status: 403 }));
    await expect(client(forbidden as typeof fetch).fetch('token')).rejects.toBeInstanceOf(
      BackendUnavailableError,
    );
  });

  it('maps network failures to a backend unavailable error', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('network');
    });
    await expect(client(fetchImpl as typeof fetch).fetch('token')).rejects.toBeInstanceOf(
      BackendUnavailableError,
    );
  });
});
