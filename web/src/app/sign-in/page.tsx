import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import { InlineNotice } from '@/components/ui/inline-notice';
import { landingPath } from '@/lib/auth/permissions';
import { getServerSession } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

import { SessionExpiryCleanup } from './session-expiry-cleanup';
import { SignInForm } from './sign-in-form';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = { title: messages.signIn.title };

interface SignInPageProps {
  searchParams: Promise<{ reason?: string | string[] }>;
}

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const state = await getServerSession();
  if (state.status === 'active') {
    redirect(landingPath(state.user.permissions ?? []));
  }

  const params = await searchParams;
  const expired = params.reason === 'expired';

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <p className="mb-6 text-center text-sm font-semibold tracking-tight text-primary">
          {messages.productName}
        </p>
        <div className="rounded-lg border border-line bg-surface p-6 sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight text-primary">
            {messages.signIn.title}
          </h1>
          <p className="mt-1 text-sm text-secondary">{messages.signIn.subtitle}</p>

          {expired ? (
            <InlineNotice tone="info" className="mt-5">
              {messages.session.ended}
            </InlineNotice>
          ) : null}

          <div className="mt-6">
            <SignInForm />
          </div>
        </div>
      </div>
      {expired ? <SessionExpiryCleanup /> : null}
    </main>
  );
}
