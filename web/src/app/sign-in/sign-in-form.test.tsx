import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { afterEach } from 'vitest';

import { SignInForm } from '@/app/sign-in/sign-in-form';
import { signInMessage } from '@/lib/messages';

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };

vi.mock('next/navigation', () => ({
  useRouter: () => router,
}));

function fill(email: string, password: string) {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
}

describe('SignInForm', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    router.replace.mockClear();
    router.refresh.mockClear();
  });

  it('shows the invalid request message with no fetch when input is empty', async () => {
    global.fetch = vi.fn();
    render(<SignInForm />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(
      await screen.findByText(signInMessage('invalid_request') as string),
    ).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('shows wrong password message for invalid credentials', async () => {
    global.fetch = vi.fn(async () =>
      Response.json({ error: 'invalid_credentials' }, { status: 401 }),
    ) as typeof fetch;

    render(<SignInForm />);
    fill('user@example.com', 'wrong');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(
      await screen.findByText(signInMessage('invalid_credentials') as string),
    ).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('shows locked account message', async () => {
    global.fetch = vi.fn(async () =>
      Response.json({ error: 'account_locked' }, { status: 423 }),
    ) as typeof fetch;

    render(<SignInForm />);
    fill('locked@example.com', 'something');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText(signInMessage('account_locked') as string)).toBeInTheDocument();
  });

  it('redirects to the BFF-supplied path after sign in', async () => {
    global.fetch = vi.fn(async () =>
      Response.json({ redirectTo: '/settings' }, { status: 200 }),
    ) as typeof fetch;

    render(<SignInForm />);
    fill('admin@example.com', 'secret');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(router.replace).toHaveBeenCalledWith('/settings');
      expect(router.refresh).toHaveBeenCalled();
    });
    const body = JSON.parse(String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]?.[1]?.body as string));

    expect(body).toEqual({ email: 'admin@example.com', password: 'secret' }); // pragma: allowlist secret
  });

  it('does not store tokens in browser storage', () => {
    render(<SignInForm />);
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });
});
