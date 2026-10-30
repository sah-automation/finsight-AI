'use client';

import { Button } from '@/components/ui/button';
import { messages } from '@/lib/messages';

export default function AuthenticatedError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-chat space-y-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight text-primary">
        {messages.results.temporarilyUnavailable}
      </h1>
      <Button onClick={reset}>{messages.actions.tryAgain}</Button>
    </div>
  );
}
