'use client';

import { useRouter } from 'next/navigation';
import { useId, useState, type FormEvent } from 'react';

import { Button } from '@/components/ui/button';
import { InlineNotice } from '@/components/ui/inline-notice';
import { Input } from '@/components/ui/input';
import {
  isSignInErrorCode,
  messages,
  signInMessage,
  type SignInErrorCode,
} from '@/lib/messages';

interface SignInResponse {
  redirectTo?: unknown;
  error?: unknown;
}

export function SignInForm() {
  const router = useRouter();
  const errorId = useId();
  const [submitting, setSubmitting] = useState(false);
  const [errorCode, setErrorCode] = useState<SignInErrorCode | null>(null);

  const errorMessage = signInMessage(errorCode);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorCode(null);

    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if (!email || !password) {
      setErrorCode('invalid_request');
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch('/api/auth/sign-in', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const body = (await response.json().catch(() => null)) as SignInResponse | null;
      const redirectTo = body?.redirectTo;

      if (
        response.ok &&
        typeof redirectTo === 'string' &&
        /^\/(?!\/)/.test(redirectTo)
      ) {
        router.replace(redirectTo);
        router.refresh();
        return;
      }
      setErrorCode(
        isSignInErrorCode(body?.error) ? body.error : 'temporarily_unavailable',
      );
    } catch {
      setErrorCode('temporarily_unavailable');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit} noValidate>
      {errorMessage ? (
        <InlineNotice tone="error">
          <span id={errorId}>{errorMessage}</span>
        </InlineNotice>
      ) : null}

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <label htmlFor="email" className="text-sm font-medium text-primary">
            {messages.signIn.emailLabel}
          </label>
          <span className="text-xs text-muted">{messages.signIn.required}</span>
        </div>
        <Input
          id="email"
          name="email"
          type="email"
          inputMode="email"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          aria-invalid={errorCode ? true : undefined}
          aria-describedby={errorMessage ? errorId : undefined}
          disabled={submitting}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <label htmlFor="password" className="text-sm font-medium text-primary">
            {messages.signIn.passwordLabel}
          </label>
          <span className="text-xs text-muted">{messages.signIn.required}</span>
        </div>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={errorCode ? true : undefined}
          aria-describedby={errorMessage ? errorId : undefined}
          disabled={submitting}
        />
      </div>

      <Button type="submit" className="w-full" disabled={submitting} aria-busy={submitting}>
        {submitting ? messages.signIn.submitting : messages.signIn.submit}
      </Button>
    </form>
  );
}
