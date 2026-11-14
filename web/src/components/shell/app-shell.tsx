import type { CurrentUser } from '@/lib/auth/current-user';
import { messages } from '@/lib/messages';

import { MobileHeader, Sidebar } from './sidebar';

export interface AppShellProps {
  user: CurrentUser;
  children: React.ReactNode;
}

export function AppShell({ user, children }: AppShellProps) {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only rounded-md bg-inverse px-4 py-2 text-sm text-inverse-text focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
      >
        {messages.navigation.skipToContent}
      </a>
      <div className="mx-auto flex min-h-screen w-full max-w-app">
        <Sidebar user={user} />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileHeader user={user} />
          <main id="main-content" className="flex-1 px-4 py-6 sm:px-6 shell:px-8 shell:py-8">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
